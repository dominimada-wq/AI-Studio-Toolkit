import csv
import os
import tempfile
from pathlib import Path
from typing import Iterable, Mapping, Sequence


class CaptionReportStorageError(Exception):
    """The caption report could not be written."""


class CaptionReportStorage:
    """
    Writes a caption length report as a CSV file at a path the user chose.

    Exchanges plain dictionaries only (Infrastructure never sees the Domain).
    Every field is quoted so that accents, double quotes, commas and line breaks
    inside the analyzed text survive a round trip through any CSV reader; the
    file is UTF-8 with a byte order mark so that spreadsheet applications detect
    the encoding. The file is written next to its destination and then moved
    into place: a failure never leaves a half-written report at the chosen path.
    """

    ENCODING = "utf-8-sig"

    @staticmethod
    def write(path, columns: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
        target = Path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            file_descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
            )
        except OSError as exc:
            raise CaptionReportStorageError(f"Could not prepare the report file {target}: {exc}") from exc
        try:
            with os.fdopen(file_descriptor, "w", encoding=CaptionReportStorage.ENCODING, newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(columns), quoting=csv.QUOTE_ALL,
                                        lineterminator="\r\n", extrasaction="raise")
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            os.replace(temporary_name, target)
        except (OSError, ValueError, csv.Error) as exc:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise CaptionReportStorageError(f"Could not write the report file {target}: {exc}") from exc
