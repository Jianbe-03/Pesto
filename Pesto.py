import traceback;
import threading;  
import argparse; 
import shutil; 
import gzip; 
import json; 
import sys;
import io; 
import os; 
import subprocess;
import tempfile;
import uuid;
import hashlib;

def ensure_dependency(module_name, package_name=None):
    if package_name is None:
        package_name = module_name
    try:
        __import__(module_name)
    except ImportError:
        print(f"Installing missing dependency: {package_name}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            print(f"Successfully installed {package_name}")
        except subprocess.CalledProcessError:
            print(f"Failed to install {package_name}. Please install it manually.")
            sys.exit(1)

ensure_dependency('requests');
ensure_dependency('yaml', 'pyyaml');
ensure_dependency('watchdog');

import requests;
import yaml; 
from watchdog.observers import Observer;
from watchdog.events import FileSystemEventHandler, FileSystemEvent;

from typing      import Any, Optional, Union, Tuple, Dict, List, Type; 
from argparse    import ArgumentParser, _SubParsersAction, Namespace; 
from http.server import BaseHTTPRequestHandler, HTTPServer; 
from threading   import Thread; 

Version = '0.1.3';

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
    # 'TwoWaySynchronize': 'Two-way synchronize data in Visual Studio Code and Roblox Studio',

    # 'ExportSynchronize': 'One-way synchronize data from Visual Studio Code to Roblox Studio',
    # 'ImportSynchronize': 'One-way synchronize data from Roblox Studio to Visual Studio Code',

    'Export'           : 'Export all data from Visual Studio Code to Roblox Studio',
    'Import'           : 'Import all data from Roblox Studio to Visual Studio Code',

    'Server'           : 'Run the server',
    'Update'           : 'Update Pesto to the latest version',
    'Uninstall'        : 'Uninstall Pesto from your system'
}; 
ArgumentsForSubparsers: List[Tuple[str, Type, str]] = [
    ('--Script',    str, 'Path to a certain script to be processed along with all its ancestry'),

    ('--Host',      str, 'Web host address of the local server to send data to'),
    ('--Port',      int, 'Port number of the local server to send data to'),

    ('--Requests',  str, 'HTTPRequest types for the handler to enable')
]; 

OneTimeConnectionServerTypes: set[str] = { 'Export', 'Import' }; 

NoDataAvailableResponse = { 'Status': 'No data available' }; 
AliveResponse = { 'Status': 'Alive', 'Version': Version }; 

Server: HTTPServer = None; 
ServerThread: Thread = None; 

Chunks: Dict[int, str] = { }; 
ExportCache: Dict[int, str] = { }; # Cache for chunked exports 
ExportStatus: Dict[str, Any] = { # Track export generation progress
    'State': 'Idle', # Idle, Processing, Ready, Error
    'Progress': 0,
    'Result': None,
    'Message': ''
};

LastSnapshot: Dict[str, str] = {} # PestoId -> Hash

# Auto Sync cache (server -> Roblox polling)
AutoCache: Dict[int, str] = {}
AutoMeta: Optional[Dict[str, Any]] = None
AutoCacheLock = threading.Lock()

# Disk index to support patches (Roblox -> server -> disk)
PestoIdToDiskPath: Dict[str, str] = {}
DiskPathToPestoId: Dict[str, str] = {}
IndexLock = threading.Lock()

# File Watcher for Smart Import / Auto Sync
ChangedPaths: set[str] = set()  # Instance folder paths changed on disk
DeletedPestoIds: set[str] = set()  # PestoIds deleted on disk
FileWatcher: Observer = None
FileWatcherLock = threading.Lock()
WatcherStarted = False  # Starts after first Roblox->disk export/import completes

def _load_properties_file(file_path: str) -> Dict[str, Any]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            if file_path.lower().endswith(('.yaml', '.yml')):
                return yaml.safe_load(f) or {}
            return json.load(f) or {}
    except Exception:
        return {}

def RebuildDiskIndex():
    """Walks BasePath and rebuilds the PestoId <-> disk folder index."""
    global PestoIdToDiskPath, DiskPathToPestoId
    with IndexLock:
        PestoIdToDiskPath.clear()
        DiskPathToPestoId.clear()

    if not os.path.isdir(BasePath):
        return

    for root, dirs, files in os.walk(BasePath):
        if PropertiesFileName in files:
            props_path = os.path.join(root, PropertiesFileName)
            props = _load_properties_file(props_path)
            pid = props.get('PestoId')
            if pid:
                with IndexLock:
                    PestoIdToDiskPath[pid] = root
                    DiskPathToPestoId[root] = pid

class PestoFileWatcher(FileSystemEventHandler):
    def __init__(self, props_filename: str, source_filename: str):
        self.props_filename = props_filename
        self.source_filename = source_filename
        
    def _get_instance_path(self, path: str) -> str:
        """Get the instance folder path from a file path"""
        if os.path.isfile(path):
            return os.path.dirname(path)
        return path
        
    def _is_relevant_file(self, path: str) -> bool:
        """Check if the file is a properties or source file"""
        basename = os.path.basename(path)
        return basename == self.props_filename or basename == self.source_filename

    def _try_index_instance_dir(self, instance_dir: str):
        props_path = os.path.join(instance_dir, self.props_filename)
        if not os.path.exists(props_path):
            return

        props = _load_properties_file(props_path)
        pid = props.get('PestoId')
        if not pid:
            return

        with IndexLock:
            PestoIdToDiskPath[pid] = instance_dir
            DiskPathToPestoId[instance_dir] = pid
        
    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if self._is_relevant_file(event.src_path):
            instance_path = self._get_instance_path(event.src_path)
            with FileWatcherLock:
                ChangedPaths.add(instance_path)
                # If this instance was previously considered deleted, undo that.
                pid = None
                with IndexLock:
                    pid = DiskPathToPestoId.get(instance_path)
                if pid:
                    DeletedPestoIds.discard(pid)
            if os.path.basename(event.src_path) == self.props_filename:
                self._try_index_instance_dir(instance_path)
            print(f"[Watcher] Modified: {instance_path}")
            
    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        if self._is_relevant_file(event.src_path):
            instance_path = self._get_instance_path(event.src_path)
            with FileWatcherLock:
                ChangedPaths.add(instance_path)
                pid = None
                with IndexLock:
                    pid = DiskPathToPestoId.get(instance_path)
                if pid:
                    DeletedPestoIds.discard(pid)
            if os.path.basename(event.src_path) == self.props_filename:
                self._try_index_instance_dir(instance_path)
            print(f"[Watcher] Created: {instance_path}")
            
    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory:
            instance_dir = event.src_path
            with FileWatcherLock:
                ChangedPaths.discard(instance_dir)
                with IndexLock:
                    pid = DiskPathToPestoId.get(instance_dir)
                    if pid:
                        DeletedPestoIds.add(pid)
                        PestoIdToDiskPath.pop(pid, None)
                        DiskPathToPestoId.pop(instance_dir, None)
            print(f"[Watcher] Deleted folder: {event.src_path}")
        elif self._is_relevant_file(event.src_path):
            instance_path = self._get_instance_path(event.src_path)
            # Only mark as deleted if the entire folder is gone
            if not os.path.exists(instance_path):
                with FileWatcherLock:
                    ChangedPaths.discard(instance_path)
                    with IndexLock:
                        pid = DiskPathToPestoId.get(instance_path)
                        if pid:
                            DeletedPestoIds.add(pid)
                            PestoIdToDiskPath.pop(pid, None)
                            DiskPathToPestoId.pop(instance_path, None)
                print(f"[Watcher] Deleted: {instance_path}")
                
    def on_moved(self, event: FileSystemEvent):
        if event.is_directory:
            with FileWatcherLock:
                ChangedPaths.add(event.dest_path)

            with IndexLock:
                pid = DiskPathToPestoId.pop(event.src_path, None)
                if pid:
                    PestoIdToDiskPath[pid] = event.dest_path
                    DiskPathToPestoId[event.dest_path] = pid
            print(f"[Watcher] Moved: {event.src_path} -> {event.dest_path}")
        elif self._is_relevant_file(event.src_path) or self._is_relevant_file(event.dest_path):
            src_instance = self._get_instance_path(event.src_path)
            dest_instance = self._get_instance_path(event.dest_path)
            with FileWatcherLock:
                ChangedPaths.add(dest_instance)

            if os.path.basename(event.dest_path) == self.props_filename:
                self._try_index_instance_dir(dest_instance)
            print(f"[Watcher] Moved file: {src_instance} -> {dest_instance}")

def StartFileWatcher(base_path: str, props_filename: str, source_filename: str):
    global FileWatcher, WatcherStarted, ChangedPaths, DeletedPestoIds
    if FileWatcher is not None or WatcherStarted:
        return
    
    # Clear any cached changes from before watcher started
    with FileWatcherLock:
        ChangedPaths.clear()
        DeletedPestoIds.clear()

    # Build the id->path index once when watcher starts
    RebuildDiskIndex()
    
    FileWatcher = Observer()
    handler = PestoFileWatcher(props_filename, source_filename)
    FileWatcher.schedule(handler, base_path, recursive=True)
    FileWatcher.start()
    WatcherStarted = True
    print(f"[Watcher] Started watching: {base_path}")

def StopFileWatcher():
    global FileWatcher, WatcherStarted
    if FileWatcher is not None:
        FileWatcher.stop()
        FileWatcher.join()
        FileWatcher = None
        WatcherStarted = False
        print("[Watcher] Stopped")

def PauseFileWatcher():
    global FileWatcher
    if FileWatcher is not None:
        FileWatcher.unschedule_all()
        print("[Watcher] Paused")

def ResumeFileWatcher(base_path: str, props_filename: str, source_filename: str):
    global FileWatcher
    if FileWatcher is not None:
        handler = PestoFileWatcher(props_filename, source_filename)
        FileWatcher.schedule(handler, base_path, recursive=True)
        print("[Watcher] Resumed")

def GetChangedInstanceData() -> Tuple[Dict[str, Any], List[str]]:
    """Get data only for changed instances and list of deleted PestoIds"""
    global ChangedPaths, DeletedPestoIds
    
    with FileWatcherLock:
        changed = list(ChangedPaths)
        deleted_ids = list(DeletedPestoIds)
        ChangedPaths.clear()
        DeletedPestoIds.clear()
    
    PN = Settings.get('PropertiesName')
    SN = Settings.get('SourceName')
    
    Hierarchy = {}
    DeletedIds = []
    
    # Process changed paths
    for path in changed:
        if os.path.exists(path):
            Hierarchy = GetInstanceDetails(path, Hierarchy)
    
    # Process deleted paths - try to find PestoId from cached data
    DeletedIds.extend(deleted_ids)
    
    return Hierarchy, DeletedIds

InboundApplyLock = threading.Lock()

def _write_properties_file(file_path: str, props: Dict[str, Any]):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            if file_path.lower().endswith(('.yaml', '.yml')):
                yaml.dump(props, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            else:
                json.dump(props, f, indent=2)
    except Exception as e:
        LogException(e, f'write properties file {file_path}!')

def ApplyDiskPatch(patch: Dict[str, Any]) -> bool:
    """Apply an inbound patch coming from Roblox -> disk. Pauses watcher during writes."""
    pid = patch.get('PestoId')
    if not pid:
        return False

    with InboundApplyLock:
        with IndexLock:
            instance_dir = PestoIdToDiskPath.get(pid)

        if not instance_dir or not os.path.isdir(instance_dir):
            return False

        PauseFileWatcher()
        try:
            if 'Source' in patch and patch['Source'] is not None:
                src_path = os.path.join(instance_dir, SourceFileName)
                with open(src_path, 'w', encoding='utf-8') as f:
                    f.write(patch['Source'])

            if 'Properties' in patch and isinstance(patch['Properties'], dict):
                props_path = os.path.join(instance_dir, PropertiesFileName)
                existing = _load_properties_file(props_path) if os.path.exists(props_path) else {}
                existing.update(patch['Properties'])
                existing['PestoId'] = pid
                _write_properties_file(props_path, existing)

            # Refresh index entry
            with IndexLock:
                PestoIdToDiskPath[pid] = instance_dir
                DiskPathToPestoId[instance_dir] = pid
        finally:
            # Small delay before resuming to ensure OS flush completes
            import time
            time.sleep(0.05)
            ResumeFileWatcher(BasePath, PropertiesFileName, SourceFileName)

    return True

def _index_subtree(start_dir: str):
    if not os.path.isdir(start_dir):
        return
    for root, _dirs, files in os.walk(start_dir):
        if PropertiesFileName in files:
            props_path = os.path.join(root, PropertiesFileName)
            props = _load_properties_file(props_path)
            pid = props.get('PestoId')
            if pid:
                with IndexLock:
                    PestoIdToDiskPath[pid] = root
                    DiskPathToPestoId[root] = pid

def ApplyDiskUpsert(parent_pesto_id: str, node: Dict[str, Any]) -> bool:
    """Create/update a subtree on disk under the given parent PestoId."""
    if not parent_pesto_id or not isinstance(node, dict):
        return False

    PN = Settings.get('PropertiesName')
    props = node.get(PN) or {}
    child_pid = props.get('PestoId')
    child_name = props.get('Name') or 'Unnamed'
    if not child_pid:
        return False

    with IndexLock:
        parent_dir = PestoIdToDiskPath.get(parent_pesto_id)

    if not parent_dir or not os.path.isdir(parent_dir):
        RebuildDiskIndex()
        with IndexLock:
            parent_dir = PestoIdToDiskPath.get(parent_pesto_id)
        if not parent_dir or not os.path.isdir(parent_dir):
            return False

    # Reuse existing path if known
    with IndexLock:
        existing_child_dir = PestoIdToDiskPath.get(child_pid)
    if existing_child_dir and os.path.isdir(existing_child_dir):
        child_dir = existing_child_dir
    else:
        # Pick a free folder name under parent
        candidate = os.path.join(parent_dir, child_name)
        child_dir = candidate
        if os.path.exists(candidate):
            # If collision, try numbered suffixes
            for i in range(2, 101):
                alt = f"{candidate} ({i})"
                if not os.path.exists(alt):
                    child_dir = alt
                    break

    with InboundApplyLock:
        PauseFileWatcher()
        try:
            os.makedirs(child_dir, exist_ok=True)
            Import(node, child_dir, True)
            _index_subtree(child_dir)
        finally:
            ResumeFileWatcher(BasePath, PropertiesFileName, SourceFileName)

    return True

def ApplyDiskDelete(pesto_id: str) -> bool:
    if not pesto_id:
        return False

    with IndexLock:
        disk_path = PestoIdToDiskPath.get(pesto_id)

    if not disk_path or not os.path.exists(disk_path):
        return False

    with InboundApplyLock:
        PauseFileWatcher()
        try:
            DeletePath(disk_path)
            with IndexLock:
                PestoIdToDiskPath.pop(pesto_id, None)
                DiskPathToPestoId.pop(disk_path, None)
        finally:
            ResumeFileWatcher(BasePath, PropertiesFileName, SourceFileName)

    return True

def PrepareAutoCachePayload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Chunk payload into AutoCache and return meta response."""
    global AutoMeta
    json_data = json.dumps(payload)

    chunk_size = 800000
    total_len = len(json_data)
    total_chunks = (total_len + chunk_size - 1) // chunk_size

    with AutoCacheLock:
        AutoCache.clear()
        for i in range(1, total_chunks + 1):
            start = (i - 1) * chunk_size
            end = min(i * chunk_size, total_len)
            AutoCache[i] = json_data[start:end]
        AutoMeta = {
            'Status': 'Ready',
            'TotalChunks': total_chunks,
            'TotalSize': total_len,
            'IsAuto': True
        }
        return AutoMeta

def ComputeHash(data: Any) -> str:
    return hashlib.md5(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

def BuildSnapshot(node: Dict[str, Any], snapshot: Dict[str, str]):
    PN = Settings.get('PropertiesName')
    SN = Settings.get('SourceName')
    
    for key, value in node.items():
        if key != PN and key != SN:
            # It's a child
            child_props = value.get(PN, {})
            child_source = value.get(SN, "")
            pesto_id = child_props.get('PestoId')
            
            if pesto_id:
                # Hash properties (excluding PestoId itself? No, include it)
                # Hash source
                combined_hash = ComputeHash(child_props) + ComputeHash(child_source)
                snapshot[pesto_id] = combined_hash
            
            BuildSnapshot(value, snapshot)

def PruneHierarchy(node: Dict[str, Any], changed_ids: set) -> Tuple[Dict[str, Any], bool]:
    PN = Settings.get('PropertiesName')
    SN = Settings.get('SourceName')
    
    pruned_node = {}
    has_relevant_content = False
    
    for key, value in node.items():
        if key == PN or key == SN:
            continue
            
        # It's a child
        child_props = value.get(PN, {})
        pesto_id = child_props.get('PestoId')
        
        is_changed = pesto_id and (pesto_id in changed_ids)
        
        pruned_child, child_has_relevant = PruneHierarchy(value, changed_ids)
        
        if is_changed or child_has_relevant:
            has_relevant_content = True
            pruned_node[key] = pruned_child
            
            if is_changed:
                # Include full data
                if PN in value: pruned_node[key][PN] = value[PN]
                if SN in value: pruned_node[key][SN] = value[SN]
            else:
                # Include minimal data (PestoId) to maintain structure
                if pesto_id:
                    pruned_node[key][PN] = {'PestoId': pesto_id}
                    
    return pruned_node, has_relevant_content


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
                    DataChannel = (self.headers.get('Pesto-Data-Channel', 'Export') or 'Export').lower()
                    AutoAction = (self.headers.get('Pesto-Auto-Action', '') or '').lower()

                    # AutoSync: Roblox -> disk patch
                    if DataChannel == 'auto' and AutoAction == 'patch':
                        if not isinstance(Data, dict):
                            self.send_error(400, 'Invalid patch body')
                            return

                        ok = ApplyDiskPatch(Data)
                        if not ok:
                            self.send_error(404, 'Patch target not found')
                            return

                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'Status': 'OK'}).encode('utf-8'))
                        return

                    # AutoSync: Roblox -> disk upsert (create/update instance subtree)
                    if DataChannel == 'auto' and AutoAction == 'upsert':
                        if not isinstance(Data, dict):
                            self.send_error(400, 'Invalid upsert body')
                            return
                        parent_pid = Data.get('ParentPestoId')
                        node = Data.get('Node')
                        ok = ApplyDiskUpsert(parent_pid, node)
                        if not ok:
                            self.send_error(404, 'Upsert target not found')
                            return
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'Status': 'OK'}).encode('utf-8'))
                        return

                    # AutoSync: Roblox -> disk delete
                    if DataChannel == 'auto' and AutoAction == 'delete':
                        if not isinstance(Data, dict):
                            self.send_error(400, 'Invalid delete body')
                            return
                        pid = Data.get('PestoId')
                        ok = ApplyDiskDelete(pid)
                        if not ok:
                            self.send_error(404, 'Delete target not found')
                            return
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'Status': 'OK'}).encode('utf-8'))
                        return

                    Index = Data['Index']; 
                    Total = Data['Total']; 
                    Chunk = Data['Chunk']; 

                    Chunks[Index] = Chunk; 

                    print(f'Successfully received data-chunk ({Index}/{Total})!'); 

                    if (len(Chunks) >= Total): 
                        # Pause file watcher during import
                        PauseFileWatcher()
                        
                        if StopAfterOneIteration and Settings.get('CleanUpBeforeImportInVSC'):
                            DeletePath(BasePath); 
                            print(f'Successfully removed all descendants of {BasePath} before importing!'); 

                        Import(json.loads(''.join(Chunks[i] for i in sorted(Chunks))), BasePath, RequestFrequency); 
                        Chunks.clear(); 

                        # Start file watcher after first import is complete
                        if not WatcherStarted:
                            StartFileWatcher(BasePath, PropertiesFileName, SourceFileName)
                        else:
                            # Resume watcher after import
                            ResumeFileWatcher(BasePath, PropertiesFileName, SourceFileName)

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
                    DataChannel = (self.headers.get('Pesto-Data-Channel', 'Export') or 'Export').lower()
                    ChunkIndex = int(self.headers.get('Pesto-Chunk-Index', 0))
                    ExportAction = self.headers.get('Pesto-Export-Action', 'Start' if ChunkIndex == 0 else 'Poll')

                    # AutoSync: Roblox polls for diffs
                    if DataChannel == 'auto':
                        AutoAction = (self.headers.get('Pesto-Auto-Action', 'AutoPoll') or 'AutoPoll')

                        if ChunkIndex == 0:
                            # Only start after baseline exists
                            if not WatcherStarted:
                                Response = PrepareAutoCachePayload({
                                    'IsAuto': True,
                                    'IsSmart': True,
                                    'Changes': {},
                                    'Deletions': [],
                                    'Message': 'AutoSync not ready: baseline not established yet.'
                                })
                            else:
                                changes, deletions = GetChangedInstanceData()
                                Response = PrepareAutoCachePayload({
                                    'IsAuto': True,
                                    'IsSmart': True,
                                    'Changes': changes,
                                    'Deletions': deletions
                                })
                        else:
                            with AutoCacheLock:
                                if ChunkIndex in AutoCache:
                                    Response = {
                                        'Chunk': AutoCache[ChunkIndex],
                                        'Index': ChunkIndex,
                                        'IsAuto': True
                                    }
                                else:
                                    self.send_error(404, 'Auto chunk not found')
                                    return
                        # Auto channel handled fully (respond immediately and return)
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        if Response is None:
                            Response = NoDataAvailableResponse
                        self.wfile.write(json.dumps(Response).encode('utf-8'))
                        if StopAfterOneIteration:
                            StopHTTPServer()
                        return

                    if ChunkIndex == 0:
                        # Handle Export Generation
                        if ExportAction == 'Start':
                            # Start new generation
                            ExportStatus['State'] = 'Processing'
                            ExportStatus['Progress'] = 0
                            ExportStatus['Message'] = 'Starting export...'
                            ExportStatus['Result'] = None
                            
                            def RunExportTask():
                                global ExportStatus, ExportCache
                                try:
                                    # Pause file watcher during export
                                    PauseFileWatcher()
                                    
                                    FullData = Export(Script)
                                    JsonData = json.dumps(FullData)
                                    
                                    # Chunk it
                                    ChunkSize = 800000 # 800KB
                                    TotalLen = len(JsonData)
                                    TotalChunks = (TotalLen + ChunkSize - 1) // ChunkSize
                                    
                                    ExportCache.clear()
                                    for i in range(1, TotalChunks + 1):
                                        Start = (i - 1) * ChunkSize
                                        End = min(i * ChunkSize, TotalLen)
                                        ExportCache[i] = JsonData[Start:End]
                                        
                                    ExportStatus['Result'] = {
                                        'Status': 'Ready',
                                        'TotalChunks': TotalChunks,
                                        'TotalSize': TotalLen
                                    }
                                    ExportStatus['State'] = 'Ready'
                                    print(f"Prepared export: {TotalLen} bytes in {TotalChunks} chunks")
                                    
                                    # Resume file watcher after export
                                    ResumeFileWatcher(BasePath, PropertiesFileName, SourceFileName)
                                except Exception as e:
                                    ExportStatus['State'] = 'Error'
                                    ExportStatus['Message'] = str(e)
                                    LogException(e, "Export Task")
                                    # Resume watcher even on error
                                    ResumeFileWatcher(BasePath, PropertiesFileName, SourceFileName)

                            threading.Thread(target=RunExportTask).start()
                            
                            Response = {
                                'Status': 'Processing',
                                'Progress': 0,
                                'Message': 'Started export generation'
                            }

                        elif ExportAction == 'SmartStart':
                            # Smart export using file watcher cached changes
                            ExportStatus['State'] = 'Processing'
                            ExportStatus['Progress'] = 0
                            ExportStatus['Message'] = 'Starting smart export...'
                            ExportStatus['Result'] = None
                            
                            def RunSmartExportTask():
                                global ExportStatus, ExportCache
                                try:
                                    # Pause file watcher during smart export
                                    PauseFileWatcher()
                                    
                                    # Get only the changed data from the file watcher
                                    ChangedData, DeletedPaths = GetChangedInstanceData()
                                    
                                    # Extract PestoIds from deleted paths
                                    DeletedIds = []
                                    for path in DeletedPaths:
                                        # Try to read the PestoId from a cached properties file
                                        # For now, just pass the path - client will handle it
                                        DeletedIds.append(path)
                                    
                                    ResultData = {
                                        'Changes': ChangedData,
                                        'Deletions': DeletedIds,
                                        'IsSmart': True
                                    }
                                    
                                    JsonData = json.dumps(ResultData)
                                    
                                    # Chunk it
                                    ChunkSize = 800000 # 800KB
                                    TotalLen = len(JsonData)
                                    TotalChunks = (TotalLen + ChunkSize - 1) // ChunkSize
                                    
                                    ExportCache.clear()
                                    for i in range(1, TotalChunks + 1):
                                        Start = (i - 1) * ChunkSize
                                        End = min(i * ChunkSize, TotalLen)
                                        ExportCache[i] = JsonData[Start:End]
                                        
                                    ExportStatus['Result'] = {
                                        'Status': 'Ready',
                                        'TotalChunks': TotalChunks,
                                        'TotalSize': TotalLen
                                    }
                                    ExportStatus['State'] = 'Ready'
                                    print(f"Prepared smart export: {TotalLen} bytes in {TotalChunks} chunks. Changes from watcher.")
                                    
                                    # Resume file watcher after smart export
                                    ResumeFileWatcher(BasePath, PropertiesFileName, SourceFileName)
                                except Exception as e:
                                    ExportStatus['State'] = 'Error'
                                    ExportStatus['Message'] = str(e)
                                    LogException(e, "Smart Export Task")
                                    # Resume watcher even on error
                                    ResumeFileWatcher(BasePath, PropertiesFileName, SourceFileName)

                            threading.Thread(target=RunSmartExportTask).start()
                            
                            Response = {
                                'Status': 'Processing',
                                'Progress': 0,
                                'Message': 'Started smart export generation'
                            }
                            
                        elif ExportAction == 'Poll':
                            if ExportStatus['State'] == 'Processing':
                                Response = {
                                    'Status': 'Processing',
                                    'Progress': ExportStatus['Progress'],
                                    'Message': f"Processed {ExportStatus['Progress']} items..."
                                }
                            elif ExportStatus['State'] == 'Ready':
                                Response = ExportStatus['Result']
                            elif ExportStatus['State'] == 'Error':
                                Response = {
                                    'Status': 'Error',
                                    'Message': ExportStatus['Message']
                                }
                            else:
                                # Idle or unknown, treat as not ready or suggest start
                                Response = {
                                    'Status': 'Idle',
                                    'Message': 'No export in progress. Send Action: Start.'
                                }
                    else:
                        # Return chunk
                        if ChunkIndex in ExportCache:
                            Response = {
                                'Chunk': ExportCache[ChunkIndex],
                                'Index': ChunkIndex
                            }
                            print(f"Sending chunk {ChunkIndex}")
                        else:
                            self.send_error(404, 'Chunk not found')
                            return 

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
    # Stop file watcher first
    StopFileWatcher()
    
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

    # 1. Scan for existing PestoIds in this directory
    ExistingIds = {} # PestoId -> DirectoryName
    if os.path.isdir(Path):
        for Item in os.listdir(Path):
            ItemPath = os.path.join(Path, Item)
            if os.path.isdir(ItemPath):
                PropsFile = os.path.join(ItemPath, PropertiesFileName)
                if os.path.exists(PropsFile):
                    try:
                        with open(PropsFile, 'r', encoding='utf-8') as f:
                            Props = yaml.safe_load(f) if UseYAML else json.load(f)
                            if Props and 'PestoId' in Props:
                                ExistingIds[Props['PestoId']] = Item
                    except:
                        pass
            
    ProcessedItems = set()

    # Group children by Name to handle duplicates
    ChildrenByName = {} # Name -> [(PestoId, Data)]
    
    # Separate Properties/Source from Children
    PropertiesData = None
    SourceData = None
    
    for Key, Value in Data.items():
        if Key == PN:
            PropertiesData = Value
        elif Key == SN:
            SourceData = Value
        else:
            # It's a child
            ChildProps = Value.get(PN, {})
            ChildName = ChildProps.get('Name', 'Unnamed')
            if ChildName not in ChildrenByName:
                ChildrenByName[ChildName] = []
            ChildrenByName[ChildName].append((Key, Value))

    # Process Properties
    if PropertiesData:
        ProcessedItems.add(PropertiesFileName)
        try:
            FilePath = os.path.join(Path, PropertiesFileName)
            Write = True
            
            if os.path.exists(FilePath):
                try:
                    with open(FilePath, 'r', encoding='utf-8') as File:
                        ExistingProps = {}
                        if UseYAML:
                            ExistingProps = yaml.safe_load(File)
                        else:
                            ExistingProps = json.load(File)
                        
                        # Preserve PestoId from existing file if present (User Request: Ignore PestoId changes after first export)
                        if ExistingProps and 'PestoId' in ExistingProps:
                            PropertiesData['PestoId'] = ExistingProps['PestoId']
                        
                        if ExistingProps == PropertiesData:
                            Write = False
                except:
                    pass
            
            if Write:
                print(f"Updating Properties: {FilePath}")
                with open(FilePath, 'w', encoding = 'utf-8') as File:
                    if UseYAML:
                        yaml.dump(PropertiesData, File, default_flow_style = False, allow_unicode = True, sort_keys = False); 

                    else:
                        json.dump(PropertiesData, File, indent = 2); 

        except Exception as e:
            LogException(e, f'write Properties File for {Path}!'); 

    # Process Source
    if SourceData:
        ProcessedItems.add(SourceFileName)
        try:
            FilePath = os.path.join(Path, SourceFileName)
            Write = True
            if os.path.exists(FilePath):
                try:
                    with open(FilePath, 'r', encoding = 'utf-8') as File:
                        if File.read() == SourceData:
                            Write = False
                except:
                    pass

            if Write:
                print(f"Updating Source: {FilePath}")
                with open(FilePath, 'w', encoding = 'utf-8') as File:
                    File.write(SourceData); 

        except Exception as e:
            LogException(e, f'write Source File for {Path}!'); 

    # Process Children
    DiskMap = {name: id for id, name in ExistingIds.items()}

    for Name, Children in ChildrenByName.items():
        # Potential filenames
        PotentialFilenames = []
        for i in range(len(Children)):
            if i == 0:
                PotentialFilenames.append(Name)
            else:
                PotentialFilenames.append(f"{Name} ({i+1})")
        
        FinalAssignments = {} # PestoId -> Filename
        RemainingChildren = []
        AvailableFilenames = set(PotentialFilenames)
        
        # Pass 1: Keep existing filenames if they are in the allowed set
        for PestoId, ChildData in Children:
            if PestoId in ExistingIds:
                CurrentName = ExistingIds[PestoId]
                if CurrentName in AvailableFilenames:
                    FinalAssignments[PestoId] = CurrentName
                    AvailableFilenames.remove(CurrentName)
                else:
                    RemainingChildren.append((PestoId, ChildData))
            else:
                RemainingChildren.append((PestoId, ChildData))
                
        # Pass 2: Assign remaining children to available filenames
        # Sort remaining children by ID for determinism
        RemainingChildren.sort(key=lambda x: x[0])
        
        SortedAvailable = sorted(list(AvailableFilenames), key=lambda x: (len(x), x))
        
        for i, (PestoId, ChildData) in enumerate(RemainingChildren):
            FinalAssignments[PestoId] = SortedAvailable[i]
            
        # Now perform the imports
        for PestoId, ChildData in Children:
            TargetName = FinalAssignments[PestoId]
            FinalPath = os.path.join(Path, TargetName)
            
            if PestoId in ExistingIds:
                OldName = ExistingIds[PestoId]
                if OldName != TargetName:
                    OldPath = os.path.join(Path, OldName)
                    
                    if os.path.exists(FinalPath):
                        # Collision! Move occupant to temp
                        TempName = f"{TargetName}_pesto_temp_{uuid.uuid4().hex}"
                        TempPath = os.path.join(Path, TempName)
                        try:
                            os.rename(FinalPath, TempPath)
                            print(f"Collision: Moved {TargetName} to {TempName}")
                            
                            # Update ExistingIds/DiskMap
                            OccupantId = DiskMap.get(TargetName)
                            if OccupantId:
                                ExistingIds[OccupantId] = TempName
                                DiskMap[TempName] = OccupantId
                                del DiskMap[TargetName]
                                
                        except OSError as e:
                            print(f"Failed to move collision {TargetName}: {e}")

                    print(f"Renaming {OldName} to {TargetName}")
                    try:
                        os.rename(OldPath, FinalPath)
                        ExistingIds[PestoId] = TargetName
                        DiskMap[TargetName] = PestoId
                        if OldName in DiskMap: del DiskMap[OldName]
                    except OSError as e:
                        print(f"Failed to rename {OldName} to {TargetName}: {e}")
            
            ProcessedItems.add(TargetName)
            os.makedirs(FinalPath, exist_ok = True); 
            Import(ChildData, FinalPath, IsLIVE); 

    # Handle Deletions
    if not IsLIVE:
        if os.path.isdir(Path):
            for Item in os.listdir(Path):
                if Item not in ProcessedItems:
                    # Skip deleting .pesto_id file
                    if Item == '.pesto_id':
                        continue
                    ToDelete = os.path.join(Path, Item)
                    print(f"Deleting {ToDelete}")
                    DeletePath(ToDelete) 

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
        AscendantPath = os.path.join(BasePath, *Ascendants[:(i + 1)]); 
        AscendantPropertiesFile = os.path.join(AscendantPath, PropertiesFileName); 
        
        # Get the PestoId from the properties file to use as the key
        AscendantKey = AscendantName  # Default to folder name
        if os.path.isfile(AscendantPropertiesFile):
            try:
                with open(AscendantPropertiesFile, 'r', encoding = 'utf-8') as File:
                    if UseYAML:
                        AscendantProps = yaml.safe_load(File); 
                    else:
                        AscendantProps = json.load(File); 
                    
                    if AscendantProps and 'PestoId' in AscendantProps:
                        AscendantKey = AscendantProps['PestoId']
            except:
                pass
        
        if AscendantKey not in Path:
            Path[AscendantKey] = { PN: { }}; 

        Path = Path[AscendantKey]; 

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
    global ExportStatus
    Hierarchy = {}; 

    if ScriptToSynchronize:
        Hierarchy = GetInstanceDetails(os.path.abspath(ScriptToSynchronize), Hierarchy); 

    else:
        # Export ALL folders with __Properties__ files, not just ones with source files
        for File, _, FileChildren in os.walk(BasePath):
            if (PropertiesFileName in FileChildren):
                Hierarchy = GetInstanceDetails(File, Hierarchy); 
                if ExportStatus['State'] == 'Processing':
                    ExportStatus['Progress'] += 1

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

    elif (Command == 'Update'):
        print("Updating Pesto...")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                print(f"Cloning latest version...")
                # Clone the repo
                subprocess.check_call(["git", "clone", "https://github.com/Jianbe-03/Pesto.git", temp_dir], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Run install.sh
                # Check for install.sh in Pesto subdirectory first (repo structure)
                install_script = os.path.join(temp_dir, "Pesto", "install.sh")
                if not os.path.exists(install_script):
                    # Fallback to root if the repo structure is flat
                    install_script = os.path.join(temp_dir, "install.sh")

                if os.path.exists(install_script):
                    os.chmod(install_script, 0o755)
                    print("Running install script...")
                    # We need to run it from the directory containing it so it finds sibling files
                    subprocess.check_call([install_script], cwd=os.path.dirname(install_script))
                    print("Pesto updated successfully!")
                else:
                    print("Error: install.sh not found in the cloned repository.")
                    sys.exit(1)
        except subprocess.CalledProcessError as e:
            print(f"Update failed during git clone or install: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Update failed: {e}")
            sys.exit(1)
        sys.exit(0)

    elif (Command == 'Uninstall'):
        Confirm = input("Are you sure you want to uninstall Pesto? This will remove the ~/.pesto directory and the 'pesto' command. (y/n): ")
        if Confirm.lower() != 'y':
            print("Uninstall cancelled.")
            sys.exit(0)
            
        InstallDir = os.path.expanduser("~/.pesto")
        BinPath = "/usr/local/bin/pesto"
        
        # Remove symlink
        if os.path.exists(BinPath) or os.path.islink(BinPath):
            try:
                os.remove(BinPath)
                print(f"Removed {BinPath}")
            except PermissionError:
                print(f"Permission denied when removing {BinPath}. Trying with sudo...")
                try:
                    os.system(f"sudo rm {BinPath}")
                    print(f"Removed {BinPath} with sudo")
                except Exception as e:
                    print(f"Failed to remove {BinPath}: {e}")
                    print(f"Please remove it manually: sudo rm {BinPath}")

        # Remove from .zshrc
        ZshRc = os.path.expanduser("~/.zshrc")
        if os.path.exists(ZshRc):
            try:
                with open(ZshRc, 'r') as f:
                    Lines = f.readlines()
                
                NewLines = [Line for Line in Lines if '.pesto' not in Line]
                
                if len(Lines) != len(NewLines):
                    with open(ZshRc, 'w') as f:
                        f.writelines(NewLines)
                    print(f"Removed Pesto from {ZshRc}")
            except Exception as e:
                print(f"Failed to update {ZshRc}: {e}")

        # Remove installation directory
        if os.path.exists(InstallDir):
            try:
                shutil.rmtree(InstallDir)
                print(f"Removed {InstallDir}")
            except Exception as e:
                print(f"Failed to remove {InstallDir}: {e}")
        
        print("Pesto has been uninstalled.")
        sys.exit(0)

    else:
        Script = (Arguments.Script); 
    
    if not IsHTTPServerRunning(ServerURL):
        ServerType = ServerType or ServerTypesForSubparsers.get(Command, Settings.get('ServerType')); 
        ServerType = ServerType.lower(); 

        os.makedirs(BasePath, exist_ok = True); 
        
        # File watcher will be started after first export/import cycle
        
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
    print(f'Running version: {Version}');
