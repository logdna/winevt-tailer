from tomlkit.toml_file import TOMLFile
import pyinstaller_versionfile
import sys
import os


def create_version_file(toml_file_name, version_file_name):
    os.makedirs(os.path.dirname(version_file_name), exist_ok=True)
    toml_doc = TOMLFile(toml_file_name).read()
    poetry = toml_doc.value['tool']['poetry']
    pyinstaller_versionfile.create_versionfile(
        output_file=version_file_name,
        version=poetry['version'],
        company_name="Mezmo Inc.",
        file_description=poetry['description'],
        internal_name=poetry['name'],
        legal_copyright='Copyright (c) 2022 Mezmo Inc.',
        original_filename=poetry['name'] + ".exe",
        product_name=poetry['description']
    )


if __name__ == '__main__':
    sys.exit(create_version_file(sys.argv[1], sys.argv[2]))
