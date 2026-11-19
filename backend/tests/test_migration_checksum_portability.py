"""A migration's checksum must not depend on the platform's line endings.

Git's autocrlf rewrites a text file on checkout. If the runner hashes raw bytes,
the same migration has one checksum on Windows and another on Linux, and a
database created on a developer's machine refuses to start on the server:

    MigrationError: checksum migrasi 1 (0001_init) berubah

The file content is identical; only \r\n versus \n differs.
"""


from tuyabot.storage import migrate


def test_checksum_ignores_line_endings(tmp_path):
    lf = tmp_path / "0001_lf.sql"
    crlf = tmp_path / "0001_crlf.sql"
    lf.write_bytes(b"CREATE TABLE t (x INTEGER);\nCREATE TABLE u (y INTEGER);\n")
    crlf.write_bytes(b"CREATE TABLE t (x INTEGER);\r\nCREATE TABLE u (y INTEGER);\r\n")

    assert migrate._checksum(lf) == migrate._checksum(crlf)


def test_checksum_still_detects_a_real_edit(tmp_path):
    first = tmp_path / "a.sql"
    second = tmp_path / "b.sql"
    first.write_bytes(b"CREATE TABLE t (x INTEGER);\n")
    second.write_bytes(b"CREATE TABLE t (x TEXT);\n")

    assert migrate._checksum(first) != migrate._checksum(second)
