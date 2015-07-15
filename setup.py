from distutils.core import setup, Extension
import glob
import os

name         = "inotify"
version      = "0.8.0"
description  = "Python inotify wrapper and enhanced inotify tool"

source_root  = "src"

packages     = ["inotify"]
extensions   = ["inotify.binding"]

# auto generated 
package_dir = dict(zip(
    packages,
    [os.path.join(source_root, p) for p in packages]
))

ext_modules = []
for ext in extensions:
    ext_root = os.path.join(source_root, *ext.split("."))
    ext_sources = []
    for root, dirs, files in os.walk(ext_root):
        c_files = filter(lambda f: f.endswith(".c"), files)
        ext_sources += [os.path.join(root, f) for f in c_files]
    ext_modules.append(Extension(ext, sources=ext_sources))
        
setup(
    name = name,
    version = version,
    description = description,
    packages = packages,
    package_dir = package_dir,
    ext_modules = ext_modules,
)
