# DNFTree
small bash tool to list dnf package dependencies as a tree structure

# Instructions
clone or download the python file script, give it some privileges with
```
chmod +x dnftree
```
and place it somewhere accessable like /usr/bin or /usr/sbin. <br>
now your all set!

# Commands

 **-a, --all**: List every installed package <br><br>
 **-u, --user, --userinstalled**: List only user-installed packages <br><br>
 **-p, --package <name>**: Show a specific package (fuzzy match) <br><br>
 **-h, --help**: Show commands and description
# Example
```
> dnftree -p bash
bash  (+ 14 dependencies)

└── bash
    ├── filesystem
    │   └── setup
    │       └── fedora-release-kde-desktop
    │           └── fedora-release-common
    │               ├── fedora-release-identity-kde-desktop
    │               │   └── fedora-release-kde-desktop
    │               ├── fedora-release-kde-desktop
    │               └── fedora-repos
    │                   ├── fedora-gpg-keys
    │                   │   └── filesystem
    │                   └── fedora-release-kde-desktop
    ├── glibc
    │   ├── filesystem
    │   ├── glibc-all-langpacks
    │   │   ├── glibc
    │   │   └── glibc-common
    │   │       ├── bash
    │   │       ├── filesystem
    │   │       └── glibc
    │   ├── glibc-common
    │   ├── glibc-gconv-extra
    │   │   ├── glibc
    │   │   └── glibc-common
    │   └── libgcc
    └── ncurses-libs
        ├── glibc
        └── ncurses-base

```
