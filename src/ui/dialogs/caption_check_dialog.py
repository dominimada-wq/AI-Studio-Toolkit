from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.engines.caption_length_check import (
    REPORT_COLUMNS,
    STATUS_OK,
    STATUS_TOO_LONG,
    STATUS_UNVERIFIABLE,
    CaptionItemResult,
    CaptionLengthReport,
    TokenizerItemCount,
    report_rows,
)
from src.infrastructure.storage.caption_report_storage import (
    CaptionReportStorage,
    CaptionReportStorageError,
)

# "Conforme" only ever means "no excessive length": it says nothing else about a caption.
_STATUS_LABELS = {
    STATUS_OK: "Conforme (longueur)",
    STATUS_TOO_LONG: "Trop longue",
    STATUS_UNVERIFIABLE: "Non vérifiable",
}
_ORIGIN_LABELS = {
    "entry": "Légende du dataset",
    "trigger_word": "Mot déclencheur (aucune légende)",
}
_COLUMNS = ("Image", "Statut", "Origine du texte", "Jetons tokenizer 1", "Jetons tokenizer 2",
            "Limite", "Ligne tronquée", "Partie tronquée (décodée)")


def _limit_of(report: CaptionLengthReport) -> Optional[int]:
    limits = {tokenizer.content_limit for tokenizer in report.tokenizers if tokenizer.usable}
    return next(iter(limits)) if len(limits) == 1 else None


def summary_text(report: CaptionLengthReport) -> str:
    """The global balance. Only a complete check with nothing over the limit may reassure, and only about length."""
    ok = report.count(STATUS_OK)
    too_long = report.count(STATUS_TOO_LONG)
    unverifiable = report.count(STATUS_UNVERIFIABLE)
    limit = _limit_of(report)
    lines = [
        f"Légendes analysées : {report.total}",
        f"Conformes (longueur) : {ok} — Trop longues : {too_long} — Non vérifiables : {unverifiable}",
    ]
    if report.reason and report.total and unverifiable == report.total:
        lines.append(f"Vérification impossible : {report.reason}")
    if report.all_conform:
        suffix = f" de {limit} jetons de contenu par ligne" if limit else ""
        lines.append(
            f"Aucune légende ne dépasse la limite{suffix}. « Conforme » signifie seulement : aucune longueur "
            f"excessive."
        )
    else:
        if too_long:
            lines.append(f"{too_long} légende(s) seront tronquées à l'entraînement.")
        if unverifiable:
            lines.append("Bilan INCOMPLET : au moins une légende n'a pas pu être vérifiée.")
        if report.total == 0:
            lines.append("Aucune image dans le dataset de cette session : rien à vérifier.")
    empty = report.empty_count
    if empty:
        lines.append(
            f"{empty} légende(s) sans aucun texte exploitable (lignes vides) : OneTrainer s'entraîne alors "
            f"sur un texte vide ; le mot déclencheur ne les remplace pas."
        )
    return "\n".join(lines)


def source_text(report: CaptionLengthReport) -> str:
    usable = [tokenizer for tokenizer in report.tokenizers if tokenizer.usable]
    if not usable:
        return "Tokenizers : non disponibles."
    parts = [f"{tokenizer.name} ({tokenizer.source})" for tokenizer in usable]
    first = usable[0]
    return (
        "Tokenizers : " + " ; ".join(parts) + f". Limite : {first.content_limit} jetons de contenu "
        f"({first.model_max_length} positions moins {first.special_tokens_per_sequence} jetons spéciaux)."
    )


def messages_text(report: CaptionLengthReport) -> str:
    """The helper's own messages (stderr, the one expected length warning excluded): never hidden."""
    if not report.helper_messages:
        return ""
    return "Messages du processus de comptage :\n" + "\n".join(report.helper_messages)


def _tokens_cell(item: CaptionItemResult, count: Optional[TokenizerItemCount]) -> str:
    if count is None or count.content_tokens is None:
        return "—"
    text = str(count.content_tokens)
    if item.line_count > 1 and count.longest_line_number is not None:
        text += f" (ligne {count.longest_line_number})"
    return text


class CaptionCheckDialog(QDialog):
    """
    Shows one CaptionLengthReport: the global balance, the source of the
    tokenizers, the helper's own messages, one row per image with its status, and
    an export to CSV. The report belongs to one session and one set of analyzed
    texts; `is_current` tells whether they are still the current ones, and a
    result that is not current is labelled as such and cannot be exported.
    """

    def __init__(self, report: CaptionLengthReport, is_current: Optional[Callable[[], bool]] = None, parent=None):
        super().__init__(parent)
        self.report = report
        self._is_current = is_current or (lambda: True)
        self.setWindowTitle(f"Vérification des légendes — {report.training_name}")
        self.resize(1080, 580)

        layout = QVBoxLayout(self)

        self.summary_label = QLabel(summary_text(report))
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.summary_label)

        self.source_label = QLabel(source_text(report))
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)

        self.messages_label = QLabel(messages_text(report))
        self.messages_label.setWordWrap(True)
        self.messages_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.messages_label.setVisible(bool(report.helper_messages))
        layout.addWidget(self.messages_label)

        self.method_label = QLabel(
            "OneTrainer lit chaque fichier de légende ligne par ligne : chaque ligne est jugée séparément "
            "(la somme de plusieurs lignes ne compte pas) et les lignes vides sont ignorées. La partie "
            "tronquée est reconstruite par décodage des jetons : elle est normalisée par le tokenizer "
            "(minuscules, espaces) et peut différer des caractères d'origine ; le texte analysé exact figure "
            "dans l'export."
        )
        self.method_label.setWordWrap(True)
        layout.addWidget(self.method_label)

        self.stale_label = QLabel("")
        self.stale_label.setWordWrap(True)
        self.stale_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.stale_label)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(list(_COLUMNS))
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self._fill_table()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.export_button = QPushButton("Exporter en CSV…")
        self.export_button.clicked.connect(self.export_csv)
        buttons.addWidget(self.export_button)
        self.close_button = QPushButton("Fermer")
        self.close_button.clicked.connect(self.accept)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.refresh_currentness()

    def _fill_table(self) -> None:
        limit = _limit_of(self.report)
        limit_text = str(limit) if limit is not None else "—"
        self.table.setRowCount(len(self.report.items))
        for row, item in enumerate(self.report.items):
            status = _STATUS_LABELS.get(item.status, item.status)
            if item.status == STATUS_OK and not item.usable_text:
                status += " — texte vide"
            if item.status == STATUS_UNVERIFIABLE and item.reason:
                status = f"{status} : {item.reason}"
            counts = [item.counts[index] if index < len(item.counts) else None for index in range(2)]
            truncated_line = ""
            truncated_text = ""
            for count in item.counts:
                if count.truncated_text is not None:
                    truncated_line = str(count.truncated_line_number)
                    truncated_text = count.truncated_text
                    break
            cells = (item.file_name, status, _ORIGIN_LABELS.get(item.origin, item.origin),
                     _tokens_cell(item, counts[0]), _tokens_cell(item, counts[1]), limit_text,
                     truncated_line, truncated_text)
            for column, value in enumerate(cells):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def refresh_currentness(self) -> bool:
        current = bool(self._is_current())
        if current:
            self.stale_label.setText("")
        else:
            self.stale_label.setText(
                "Ce résultat n'est plus actuel : la session, le dataset, les légendes, le mot déclencheur "
                "ou l'architecture ont changé depuis l'analyse. Relancez la vérification."
            )
        self.export_button.setEnabled(current)
        return current

    def export_csv(self) -> None:
        if not self.refresh_currentness():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la vérification des légendes", "verification_legendes.csv", "Fichier CSV (*.csv)"
        )
        if not path:
            return
        try:
            CaptionReportStorage.write(path, REPORT_COLUMNS, report_rows(self.report))
        except CaptionReportStorageError as exc:
            QMessageBox.critical(self, "Export impossible", str(exc))
            return
        QMessageBox.information(self, "Export terminé", f"Fichier écrit : {path}")
