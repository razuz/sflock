# Copyright (C) 2015-2016 Jurriaan Bremer.
# This file is part of SFlock - http://www.sflock.org/.
# See the file 'docs/LICENSE.txt' for copying permission.

import zipfile
from StringIO import StringIO

from sflock.abstracts import File, Unpacker
from sflock.config import iter_passwords
from sflock.exception import UnpackException
from sflock.pick import picker
from sflock.signatures import Signatures

class ZipFile(Unpacker):
    name = "zipfile"
    exts = ".zip"

    def init(self):
        self.known_passwords = set()

    @staticmethod
    def supported():
        return True

    def handles(self):
        if picker(self.f.filepath) == "zipfile":
            return True

        if self.f.contents:
            return self._is_zipfile(self.f.contents)
        else:
            return zipfile.is_zipfile(self.f.filepath)

    def _bruteforce(self, archive, entry, passwords):
        for password in passwords:
            try:
                archive.setpassword(password)
                ret = File(entry.filename, archive.read(entry),
                           password=password)
                self.known_passwords.add(password)
                return ret
            except (RuntimeError, zipfile.BadZipfile) as e:
                msg = e.message or e.args[0]
                if "Bad password" not in msg and "Bad CRC-32" not in msg:
                    raise UnpackException("Unknown zipfile error: %s" % e)

    def _decrypt(self, archive, entry, password):
        try:
            archive.setpassword(password)
            return File(entry.filename, archive.read(entry),
                        password=password)
        except RuntimeError as e:
            if "password required" not in e.args[0] and \
                    "Bad password" not in e.args[0]:
                raise UnpackException("Unknown zipfile error: %s" % e)

        # Bruteforce the password. First try all passwords that are known to
        # work and if that fails try our entire dictionary.
        return (
            self._bruteforce(archive, entry, self.known_passwords) or
            self._bruteforce(archive, entry, iter_passwords()) or
            File(entry.filename, None, mode="failed",
                 description="Error decrypting file")
        )

    def unpack(self, mode=None, password=None, duplicates=None):
        if self.f.contents:
            archive = zipfile.ZipFile(StringIO(self.f.contents))
        else:
            archive = zipfile.ZipFile(self.f.filepath)

        if not isinstance(duplicates, list):
            duplicates = []

        entries = []
        for entry in archive.infolist():
            if entry.filename.endswith("/"):
                continue

            f = self._decrypt(archive, entry, password)

            if f.sha256 not in duplicates:
                duplicates.append(f.sha256)
            else:
                f.duplicate = True

            entries.append(f)

        return self.process(entries, duplicates)

    def _is_zipfile(self, contents):
        for k, v in Signatures.signatures.items():
            if contents.startswith(k) and v["unpacker"] == "zipfile":
                return v
