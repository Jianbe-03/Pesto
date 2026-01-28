# Pesto Agent Guide

This document provides instructions for AI agents working with Pesto-managed Roblox projects.

## Overview

Pesto is a sync tool that manages Roblox projects as a file-based structure on disk. Each Roblox instance is represented as a folder containing:
- `__Properties__.yaml` (or `.json`) - Instance properties including Name, ClassName, PestoId, Parent, etc.
- `__Source__.luau` - Source code for Script, LocalScript, and ModuleScript instances

## Pesto Commands

### Server Commands
```bash
# Start the sync server (bidirectional sync)
pesto Server

# Export from VSCode to Roblox
pesto Export

# Import from Roblox to VSCode
pesto Import
```

### Instance Management
```bash
# Create a new instance
pesto Create --Class <ClassName> --Parent <ParentPath>
# Examples:
pesto Create --Class Script --Parent ./src/ServerScriptService
pesto Create --Class ModuleScript --Parent ./src/ReplicatedStorage/Modules
pesto Create --Class Part --Parent ./src/Workspace

# Move an instance to a new parent
pesto Move --Item <ItemPath> --NewParent <NewParentPath>
# Example:
pesto Move --Item ./src/ServerScriptService/OldScript --NewParent ./src/ReplicatedStorage

# Rename an instance
pesto Rename --Item <ItemPath> --Name <NewName>
# Example:
pesto Rename --Item ./src/ServerScriptService/Script --Name "MainGameScript"
```

### Testing
```bash
# Start a test session
pesto Test --Mode run
pesto Test --Mode play
pesto Test --Mode server
```

## File Structure

A typical Pesto project looks like:
```
project/
├── Settings.yaml           # Pesto configuration
├── .pesto_id              # Universe binding (do not modify)
├── sourcemap.json         # Auto-generated sourcemap for luau-lsp
├── src/
│   ├── ServerScriptService/
│   │   ├── __Properties__.yaml
│   │   └── GameScript/
│   │       ├── __Properties__.yaml
│   │       └── __Source__.luau
│   ├── ReplicatedStorage/
│   │   ├── __Properties__.yaml
│   │   └── Modules/
│   │       └── ...
│   └── Workspace/
│       └── ...
└── Agents.md              # This file
```

## Properties File Format

Example `__Properties__.yaml`:
```yaml
Archivable: true
ClassName: Script
Name: MainScript
PestoId: abc123-def456-...
Parent: ServerScriptService
Disabled: false
```

## Important Rules for Agents

1. **Never modify PestoId** - This is a unique identifier that links disk files to Roblox instances.

2. **Use Pesto commands** for structural changes:
   - Use `pesto Move` instead of manually moving folders
   - Use `pesto Rename` instead of manually renaming folders
   - Use `pesto Create` instead of manually creating instance structures

3. **Safe to edit directly**:
   - `__Source__.luau` files (source code)
   - Properties in `__Properties__.yaml` (except PestoId)

4. **Parent property** - This should match the Name property of the parent instance, not the folder name.

5. **Sourcemap** - The `sourcemap.json` is auto-generated. Use it for type information with luau-lsp.

## Common Tasks

### Adding a New Script
```bash
pesto Create --Class Script --Parent ./src/ServerScriptService
```
Then edit the generated `__Source__.luau` file.

### Reorganizing Code
```bash
# Move a module to a different location
pesto Move --Item ./src/ServerScriptService/Utils --NewParent ./src/ReplicatedStorage

# Rename for clarity
pesto Rename --Item ./src/ReplicatedStorage/Utils --Name "SharedUtilities"
```

### Creating Module Hierarchies
```bash
# Create parent folder (as a Folder instance)
pesto Create --Class Folder --Parent ./src/ReplicatedStorage

# Rename it
pesto Rename --Item ./src/ReplicatedStorage/Folder --Name "GameModules"

# Add modules inside
pesto Create --Class ModuleScript --Parent ./src/ReplicatedStorage/GameModules
```

## Settings Reference

The `Settings.yaml` file controls Pesto behavior:
```yaml
ServerHost: localhost
ServerPort: 6969
PropertiesName: __Properties__
SourceName: __Source__
PropertiesFileExtension: yaml
SourceFileExtension: luau
FoldersUseInstanceName: true
```

## Debugging Tips

- Check the Pesto server output for sync errors
- Verify PestoId values are unique
- Ensure Parent properties match actual parent Names
- Use `pesto Server` with verbose mode for detailed logging