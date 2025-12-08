import traceback;
import threading;  
import argparse; 
import requests; 
import shutil; 
import gzip; 
import json; 
import yaml; 
import sys;
import io; 
import os; 

from typing      import Any, Optional, Union, Tuple, Dict, List, Type; 
from argparse    import ArgumentParser, _SubParsersAction, Namespace; 
from http.server import BaseHTTPRequestHandler, HTTPServer; 
from threading   import Thread; 



ScriptPath: str = os.getcwd(); 
BasePath: str = ScriptPath; 

def ValidateUniverse(UniverseId: str) -> (bool):
    if not UniverseId or UniverseId == "0":
        # Allow if UniverseId is 0 (unpublished game) or missing, but warn
        print(f"Warning: Request received with invalid Universe ID: {UniverseId}")
        return True

    ConfigPath = os.path.join(BasePath, '.pesto_id')
    
    if os.path.exists(ConfigPath):
        with open(ConfigPath, 'r') as f:
            SavedId = f.read().strip()
            if SavedId != UniverseId:
                print(f"Security Alert: Blocked request from Universe {UniverseId}. This directory is bound to Universe {SavedId}.")
                return False
            return True
    else:
        with open(ConfigPath, 'w') as f:
            f.write(UniverseId)
        print(f"Directory bound to Universe ID: {UniverseId}")
        return True 

ServerTypesForSubparsers: Dict[str, str] = {
    'TwoWaySynchronize': 'POST GET',

    'ExportSynchronize': 'GET',
    'ImportSynchronize': 'POST',

    'Export'           : 'GET',
    'Import'           : 'POST',

    'Server'           : 'POST GET'
}; 
DescriptionsForSubparsers: Dict[str, str] = {
    'TwoWaySynchronize': 'Two-way synchronize data in Visual Studio Code and Roblox Studio',

    'ExportSynchronize': 'One-way synchronize data from Visual Studio Code to Roblox Studio',
    'ImportSynchronize': 'One-way synchronize data from Roblox Studio to Visual Studio Code',

    'Export'           : 'Export all data from Visual Studio Code to Roblox Studio',
    'Import'           : 'Import all data from Roblox Studio to Visual Studio Code',

    'Server'           : 'Run the server'
}; 
ArgumentsForSubparsers: List[Tuple[str, Type, str]] = [
    ('--Script',    str, 'Path to a certain script to be processed along with all its ancestry'),

    ('--Host',      str, 'Web host address of the local server to send data to'),
    ('--Port',      int, 'Port number of the local server to send data to'),

    ('--Requests',  str, 'HTTPRequest types for the handler to enable')
]; 

OneTimeConnectionServerTypes: set[str] = { 'Export', 'Import' }; 

NoDataAvailableResponse = { 'Status': 'No data available' }; 
AliveResponse = { 'Status': 'Alive' }; 

Server: HTTPServer = None; 
ServerThread: Thread = None; 

Chunks: Dict[int, str] = { }; 



def GetHandler(POSTEnabled: Optional[bool] = True, GETEnabled: Optional[bool] = True, StopAfterOneIteration: Optional[bool] = True):
    class RequestHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> (None):
            global Settings; 

            try:
                if not POSTEnabled:
                    self.send_error(405, 'POST method not allowed'); 

                    return; 

                OK = True; 

                UniverseId = self.headers.get('Roblox-Universe-Id', '')
                if not ValidateUniverse(UniverseId):
                    self.send_error(403, 'Forbidden: Universe ID mismatch')
                    return

                StatusHeader = Settings.get('StatusHeader'); 
                SettingsHeader = Settings.get('SettingsHeader'); 
                DataHeader = Settings.get('DataHeader'); 
                LIVEHeader = Settings.get('LIVEHeader'); 

                TypeHeaderName = list(DataHeader.keys())[0]; 
                FrequencyHeaderName = list(LIVEHeader.keys())[0]; 

                RequestType = self.headers.get(TypeHeaderName, '').lower(); 
                RequestFrequency = (self.headers.get(FrequencyHeaderName, '').lower() == LIVEHeader[FrequencyHeaderName]); 

                Data = self.rfile.read(int(self.headers['Content-Length'])); 

                if IsDataGZipped(Data):
                    with gzip.GzipFile(fileobj = io.BytesIO(Data), mode = 'rb') as File:
                        Data = File.read(); 

                if (RequestType != StatusHeader[TypeHeaderName].lower()):
                    Data = json.loads(Data.decode('utf-8')); 

                if (RequestType == SettingsHeader[TypeHeaderName].lower()):
                    Settings = Data; 

                elif (RequestType == DataHeader[TypeHeaderName].lower()):
                    Index = Data['Index']; 
                    Total = Data['Total']; 
                    Chunk = Data['Chunk']; 

                    Chunks[Index] = Chunk; 

                    print(f'Successfully received data-chunk ({Index}/{Total})!'); 

                    if (len(Chunks) >= Total): 
                        if StopAfterOneIteration and Settings.get('CleanUpBeforeImportInVSC'):
                            DeletePath(BasePath); 
                            print(f'Successfully removed all descendants of {BasePath} before importing!'); 

                        Import(json.loads(''.join(Chunks[i] for i in sorted(Chunks))), BasePath, RequestFrequency); 
                        Chunks.clear(); 

                        print('Successfully reconstructed hierarchy!');  
                
                elif (RequestType == StatusHeader[TypeHeaderName].lower()):
                    pass; 
                
                else:
                    self.send_error(400, f'\'{TypeHeaderName}\' Header either not passed or incorrect ({RequestType}). Please try again using {DataHeader}, {SettingsHeader} or {StatusHeader}.'); 
                    
                    OK = False; 
            
                if OK:
                    self.send_response(200); 
                    self.end_headers(); 

            except Exception as e:
                self.send_error(500, 'Unexpected error'); 

                LogException(e, 'reconstruct hierarchy!'); 

            if StopAfterOneIteration:
                StopHTTPServer(); 

        def do_GET(self) -> (None):
            global Settings; 
        
            try:
                if not GETEnabled:
                    self.send_error(405, 'GET method not allowed'); 

                    return; 

                OK = True; 

                UniverseId = self.headers.get('Roblox-Universe-Id', '')
                if not ValidateUniverse(UniverseId):
                    self.send_error(403, 'Forbidden: Universe ID mismatch')
                    return

                StatusHeader = Settings.get('StatusHeader'); 
                SettingsHeader = Settings.get('SettingsHeader'); 
                DataHeader = Settings.get('DataHeader'); 
                TypeHeaderName = list(DataHeader.keys())[0]; 

                RequestType = self.headers.get(TypeHeaderName, '').lower();  

                Response = None; 

                if (RequestType == SettingsHeader[TypeHeaderName].lower()):
                    Response = Settings; 
                
                elif (RequestType == DataHeader[TypeHeaderName].lower()):
                    Response = Export(Script); 

                elif (RequestType == StatusHeader[TypeHeaderName].lower()):
                    Response = AliveResponse; 

                else:
                    self.send_error(400, f'\'{TypeHeaderName}\' Header either not passed or incorrect ({RequestType}). Please try again using {DataHeader}, {SettingsHeader} or {StatusHeader}.'); 
                    
                    OK = False; 

                if OK:
                    self.send_response(200); 
                    self.send_header('Content-Type', 'application/json'); 
                    self.end_headers(); 

                if Response is None:
                    Response = NoDataAvailableResponse; 
                
                self.wfile.write(json.dumps(Response).encode('utf-8')); 

            except Exception as e:
                self.send_error(500, 'Unexpected error'); 

                LogException(e, 'send hierarchy data over!'); 

            if StopAfterOneIteration:
                StopHTTPServer(); 

    return RequestHandler; 



def LogException(e: Exception, ErrorDescription: str) -> (None):
    print(f'An error occurred whilst trying to {ErrorDescription}\n'); 
    print(f'Exception Type: {(type(e).__name__)}'); 
    print(f'Exception Message: {str(e)}\n'); 
    print(''.join(traceback.format_exception(type(e), e, (e.__traceback__)))); 

def IsDataGZipped(Data: str) -> (bool):
    return (Data[:2] == b'\x1f\x8b'); 

def DeletePath(Path: str) -> (None):
    if os.path.isdir(Path):
        shutil.rmtree(Path); 
    
    else:
        os.remove(Path); 

def StopHTTPServer() -> (None):
    if Server:
        try: 
            Server.shutdown(); 

            print('Successfully stopped the running server!'); 

            sys.exit(0); 

        except Exception as e:
            LogException(e, 'stop the running server!'); 

            sys.exit(1); 

    else:
        print('The server tried to stop running, yet it already had.'); 

        sys.exit(0); 

def IsHTTPServerRunning(ServerURL: str) -> (bool):
    try:
        POSTResponse = requests.post(ServerURL, timeout = 1.0); 
        GETResponse = requests.get(ServerURL, timeout = 1.0); 

        return ((POSTResponse.status_code) == 200) or ((GETResponse.status_code) == 200); 

    except (requests.exceptions.RequestException):
        pass; 

    except Exception as e: 
        LogException(e, 'verify if the server is running!'); 

    return False; 

def LoadSettings() -> (Dict[str, Union[int, str, set[str]]]):
    try:
        # Try loading from current working directory first
        LocalSettingsPath = os.path.join(ScriptPath, 'Settings.yaml')
        if os.path.exists(LocalSettingsPath):
            with open(LocalSettingsPath, 'r') as File:
                return yaml.safe_load(File)
        
        # Fallback to the directory where Pesto.py is located (Global Install)
        GlobalSettingsPath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Settings.yaml')
        if os.path.exists(GlobalSettingsPath):
             with open(GlobalSettingsPath, 'r') as File:
                return yaml.safe_load(File)

        print('Successfully accessed the configuration file\'s data!'); 

        print('Successfully accessed the configuration file\'s data!'); 

    except Exception as e:
        LogException(e, 'access the configuration file\'s data!'); 

def Import(Data: Dict[str, Any], Path: str = BasePath, IsLIVE: bool = False) -> (None):
    PN = Settings.get('PropertiesName'); 
    SN = Settings.get('SourceName'); 

    if not IsLIVE and Settings.get('CleanUpBeforeImportInVSC'):
        if os.path.isdir(BasePath):
            for ImportedServiceFolder in os.listdir(BasePath):
                DeletePath(os.path.join(BasePath, ImportedServiceFolder)); 
            
    for Key, Value in Data.items():
        NewPath = os.path.join(Path, Key); 

        if (Key == SN):
            try:
                with open(os.path.join(Path, SourceFileName), 'w', encoding = 'utf-8') as File:
                    File.write(Value); 

            except Exception as e:
                LogException(e, f'write Source File for {Path}!'); 

        elif (Key == PN):
            try:
                with open(os.path.join(Path, PropertiesFileName), 'w', encoding = 'utf-8') as File:
                    if UseYAML:
                        yaml.dump(Value, File, default_flow_style = False, allow_unicode = True, sort_keys = False); 

                    else:
                        json.dump(Value, File, indent = 2); 

            except Exception as e:
                LogException(e, f'write Properties File for {Path}!'); 
        
        else:
            os.makedirs(NewPath, exist_ok = True); 
            Import(Value, NewPath); 

def GetInstanceDetails(InstanceFullPath: str, Hierarchy: Dict[str, Any]) -> (Dict[str, Any]):
    PN = Settings.get('PropertiesName'); 
    SN = Settings.get('SourceName'); 

    PropertyBlacklist = Settings.get('ExportFromRSPropertyBlacklist'); 
    Properties = os.path.join(InstanceFullPath, PropertiesFileName); 

    try:
        with open(Properties, 'r', encoding = 'utf-8') as File:
            if UseYAML:
                Properties = yaml.safe_load(File); 

            else:
                Properties = json.load(File); 

    except Exception as e:
        LogException(e, f'read {Properties}!'); 

        return Hierarchy; 

    Ascendants = os.path.relpath(InstanceFullPath, BasePath).split(os.sep); 
    Path = Hierarchy; 

    for i, AscendantName in enumerate(Ascendants):
        if AscendantName not in Path:
            Path[AscendantName] = { PN: { }}; 

        Path = Path[AscendantName]; 

        AscendantPath = os.path.join(BasePath, *Ascendants[:(i + 1)]); 
        AscendantPropertiesFile = os.path.join(AscendantPath, PropertiesFileName); 
        AscendantSourceFile = os.path.join(AscendantPath, SourceFileName); 

        if os.path.isfile(AscendantPropertiesFile):
            if os.path.exists(AscendantSourceFile):
                try: 
                    with open(AscendantSourceFile, 'r', encoding = 'utf-8') as File:
                        DescendantSource = File.read(); 

                except Exception as e:
                    LogException(e, f'read {AscendantSourceFile}!'); 

                    continue; 

                if (len(DescendantSource) < Settings.get('MaximumRSScriptLength')):
                        Path[SN] = DescendantSource; 

                else:
                    if Settings.get('ExportFromVSCMaximumLength'):
                        Path[SN] = '---> Source was over 199,999 and therefore excluded according to the software\'s specified settings. This is not a deliberate limit and derives from Roblox Studio\'s own limitations.'; 

                    else:
                        Path[SN] = DescendantSource; 

            try:
                with open(AscendantPropertiesFile, 'r', encoding = 'utf-8') as File:
                    if UseYAML:
                        DescendantProperties = yaml.safe_load(File); 

                    else:
                        DescendantProperties = json.load(File); 

            except Exception as e:
                LogException(e, f'trying to read {AscendantPropertiesFile}!'); 
                
                continue; 

            for Property, Value in DescendantProperties.items():
                if Property not in PropertyBlacklist:
                    Path[PN][Property] = Value; 

    return Hierarchy; 

def Export(ScriptToSynchronize: Optional[str] = None) -> (Dict[str, Any]):
    Hierarchy = {}; 

    if ScriptToSynchronize:
        Hierarchy = GetInstanceDetails(os.path.abspath(ScriptToSynchronize), Hierarchy); 

    else:
        for File, _, FileChildren in os.walk(BasePath):
            if (SourceFileName in FileChildren):
                Hierarchy = GetInstanceDetails(File, Hierarchy); 

    return Hierarchy; 



if (__name__ == '__main__'):
    Parser: ArgumentParser = argparse.ArgumentParser(description = 'Export or run a server for synchronizing uni or bilaterally from or to Roblox Studio'); 
    Subparsers: _SubParsersAction = Parser.add_subparsers(dest = 'command', required = True, help = 'Command to run'); 

    for CommandName, CommandDescription in DescriptionsForSubparsers.items():
        Subparser: ArgumentParser = Subparsers.add_parser(CommandName, help = CommandDescription); 
        Subset: List[Tuple[str, Type, str]] = ArgumentsForSubparsers[-3:] if (CommandName == 'Server') else ArgumentsForSubparsers; 

        for ArgumentName, ArgumentType, ArgumentDescription in Subset:
            Subparser.add_argument(ArgumentName, type = ArgumentType, help = ArgumentDescription); 

    Arguments: Namespace = Parser.parse_args(); 
    Settings: Dict[str, Union[int, str, set[str]]] = LoadSettings(); 

    Command: str = Arguments.command.capitalize(); 
    
    Host: str = (Arguments.Host) or Settings.get('ServerHost'); 
    Port: int = (Arguments.Port) or Settings.get('ServerPort'); 

    ServerURL: str = f'http://{Host}:{Port}'; 
    ServerType: str = None; 

    Script: str = None; 

    PN: str = Settings.get('PropertiesName'); 
    SN: str = Settings.get('SourceName'); 

    PropertiesFileExtension: str = Settings.get('PropertiesFileExtension').lower(); 

    PropertiesFileName: str = f'{PN}.{PropertiesFileExtension}'; 
    SourceFileName: str = f'{SN}.{Settings.get('SourceFileExtension').lower()}'; 

    UseYAML: bool = 'y' in PropertiesFileExtension; 
    DataSharingMessage: str = ''; 

    if (Command == 'Server'):
        ServerType = (Arguments.Requests); 

    else:
        Script = (Arguments.Script); 
    
    if not IsHTTPServerRunning(ServerURL):
        ServerType = ServerType or ServerTypesForSubparsers.get(Command, Settings.get('ServerType')); 
        ServerType = ServerType.lower(); 

        os.makedirs(BasePath, exist_ok = True); 
        
        Server = HTTPServer(
            (Host, Port),
            GetHandler(('p' in ServerType), ('g' in ServerType), (Command in OneTimeConnectionServerTypes))
        ); 
        ServerThread = threading.Thread(
            target = lambda: Server.serve_forever(),
        ); 
        ServerThread.start(); 

        print(f'Successfully started server! - Running on {ServerURL}.'); 

    else:
        print(f'The server is already running on {ServerURL}!'); 

    if ('synchronize' in Command):
        print('[LIVE CONNECTION]'); 

    else: 
        print('[SINGLE-TIME CONNECTION]'); 

    if ('Export' in Command):
        DataSharingMessage = '->'; 

    elif ('Import' in Command):
        DataSharingMessage = '<-'; 

    else:
        DataSharingMessage = '<->'; 

    print(f'Visual Studio Code {DataSharingMessage} Roblox Studio'); 
