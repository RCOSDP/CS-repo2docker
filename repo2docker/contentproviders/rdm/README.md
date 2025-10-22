# RDM Content Provider

## Overview

This content provider is used to create a Jupyter notebook server from a GakuNin RDM project.

## Configuration

### Folder Mapping Configuration File: `paths.yaml`

When setting up an analysis environment from a GakuNin RDM project, the `paths.yaml` file can be used to specify which files should be copied into the image and which should be symbolically linked. This file explicitly lists file paths and directories and defines whether each path should be copied or symlinked.

The `paths.yaml` file serves a similar purpose to the `fstab` file in Linux, mapping folders in the GakuNin RDM project to appropriate locations within the image. It should be placed in the `.binder` or `binder` directory, and the image builder (`repo2docker`) will prioritize loading from these locations to automatically apply the necessary copy and symlink settings.

The syntax of `paths.yaml` is based on the `volumes` section in Docker Compose file specifications:
https://docs.docker.com/reference/compose-file/volumes/

An example `paths.yaml` is shown below:

```yaml
override: true
paths:
    - type: copy
      source: $default_storage_path/custom-home-dir
      target: .
    - type: link
      source: /googledrive/subdir
      target: ./external/googledrive
```

In the example above, `$default_storage_path/custom-home-dir` is copied to the root directory of the image, and `/googledrive/subdir` is symlinked to `./external/googledrive` within the image.

The `paths.yaml` file is written in YAML format as a dictionary. The top-level dictionary must include the following elements:

* `override`: Set to `true` to disable the default folder mapping (which copies the default storage content to the current directory). If omitted, it is treated as `false`.
* `paths`: A list defining how each file or folder should be handled. Each item is a dictionary specifying the behavior for a specific path.

When `paths.yaml` is present, repo2docker renders the mapping into a `provision.sh` script inside the same `.binder` (or `binder`) directory in the built image. The script contains the `cp` and `ln -s` commands derived from each entry and is executed during container start-up to materialize the requested copy/link layout in the runtime home directory.

#### Elements in the `paths` List

Each item in the `paths` list is a dictionary containing the following keys:

* `type`: Specifies the operation to apply to the folder. Must be either `copy` (copies files from the source) or `link` (creates a symbolic link).
* `source`: The path to the file/folder within the GakuNin RDM project. For example, to specify a folder named `testdir` in a Google Drive storage provider, use `/googledrive/testdir`. The variable `$default_storage_path` can be used to refer to the project’s default storage (note: the default storage is not necessarily `osfstorage`, depending on the institution).
* `target`: Specifies where the file/folder should be placed in the analysis environment. This must be a relative path from the output directory (the home directory when the environment starts). To explicitly indicate a relative path, only paths starting with `.` or `./` are allowed.

> Absolute paths are not allowed for `target`, to prevent the injection of unauthorized executables into the `repo2docker` environment.

If no `paths.yaml` is provided, the default behavior is as follows:

```yaml
paths:
    - type: copy
      source: $default_storage_path
      target: .
```

## Running provision.sh with JupyterHub

When deploying repo2docker-built images with JupyterHub, you can automatically execute the `provision.sh` script at container startup to provision RDM data.

### Background Execution to Avoid Timeout

Since copying large datasets may take time and cause JupyterHub spawn timeout, the `provision.sh` script supports background execution mode. When called with command-line arguments, it will:

1. Start provisioning (copy/link operations) in the background
2. Immediately execute the passed command (e.g., `jupyterhub-singleuser`)

This allows the JupyterHub server to start while data provisioning continues in the background.

### JupyterHub Configuration

Configure your JupyterHub spawner to execute `provision.sh` if it exists:

#### KubeSpawner Example

```python
# In jupyterhub_config.py
c.KubeSpawner.cmd = [
    'bash', '-c',
    '''
    set -e

    # Find and execute provision.sh if it exists
    for path in \
        "${REPO_DIR}/binder/provision.sh" \
        "${REPO_DIR}/.binder/provision.sh" \
        "$HOME/binder/provision.sh" \
        "$HOME/.binder/provision.sh"; do

        if [ -f "$path" ]; then
            echo "[provision-wrapper] Executing: $path" >&2
            exec bash "$path" "$@"
        fi
    done

    # No provision.sh found, start normally
    exec "$@"
    ''',
    '--', 'jupyterhub-singleuser'
]
```

#### DockerSpawner Example

```python
# In jupyterhub_config.py
c.DockerSpawner.cmd = [
    'bash', '-c',
    '''
    set -e
    for path in \
        "${REPO_DIR}/binder/provision.sh" \
        "${REPO_DIR}/.binder/provision.sh" \
        "$HOME/binder/provision.sh" \
        "$HOME/.binder/provision.sh"; do
        [ -f "$path" ] && exec bash "$path" "$@"
    done
    exec "$@"
    ''',
    '--', 'jupyterhub-singleuser'
]
```

### How provision.sh Works

The generated `provision.sh` script accepts command-line arguments and has the following structure:

```bash
#!/bin/bash
set -e

# Run provisioning in background
{
    # Copy and link operations
    mkdir -p './target/path/'
    cp -fr '/mnt/rdm/storage/data/'* './target/path/'
    ln -s '/mnt/rdm/large-data/' './data'
} &

# Execute passed command if provided
if [ $# -gt 0 ]; then
    exec "$@"
fi
```

**Note**: If `/mnt/rdm/` does not exist but `/mnt/rdms/{project_id}/` is available, the build process or provisioning process will automatically create a symlink from `/mnt/rdm` to `/mnt/rdms/{project_id}`.

### Monitoring Provisioning Progress

Users can check the provisioning progress from within the Jupyter environment:

```bash
# View the provisioning log in real-time
tail -f /tmp/provision.log

# Check if provisioning is complete
grep "completed" /tmp/provision.log
```

The log file `/tmp/provision.log` contains:
- Start and completion timestamps
- Each copy/link operation with source and target paths
- Detailed command output (from `set -x`)
- Any errors that occur during provisioning

### Notes

- The `REPO_DIR` environment variable points to the repository directory (default: `/home/jovyan`)
- Provisioning runs in the background, so large data copies won't block JupyterHub startup
- Symbolic links are created immediately and are available right away
- Check `/tmp/provision.log` for provisioning progress and errors
- Container logs will show when provisioning starts and how to monitor it
