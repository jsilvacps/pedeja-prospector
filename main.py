import csv
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from PySide6.QtCore import Qt, QRectF, QSize, QThread, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPixmap,
    QIcon,
    QClipboard,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

# ── Constants ──────────────────────────────────────────────────────────────────
APP_NAME = "PedeJá Prospector"
APP_VERSION = "1.0"
APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "PedeJaProspector"
APP_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DIR / "leads.db"
CONFIG_PATH = APP_DIR / "config.json"
ASSETS_DIR = Path(__file__).parent / "assets"

def _load_estados_cidades() -> dict[str, list[str]]:
    """Carrega todos os municípios brasileiros do IBGE (assets/municipios.json).
    Fallback para lista mínima caso o arquivo não exista."""
    json_path = ASSETS_DIR / "municipios.json"
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Fallback mínimo
    return {
        "SP": ["São Paulo", "Campinas", "Santos"],
        "RJ": ["Rio de Janeiro", "Niterói"],
        "MG": ["Belo Horizonte", "Uberlândia"],
        "PR": ["Curitiba", "Londrina"],
        "RS": ["Porto Alegre", "Caxias do Sul"],
        "BA": ["Salvador"],
        "DF": ["Brasília"],
    }

ESTADOS_CIDADES: dict[str, list[str]] = _load_estados_cidades()

DEFAULT_MESSAGE = """Olá, tudo bem?

Meu nome é Jean e gostaria de apresentar o PedeJá.

O PedeJá não é apenas um cardápio digital. É uma plataforma completa para auxiliar no dia a dia do estabelecimento, com pedidos organizados pelo WhatsApp, controle de caixa, controle de estoque, relatórios de vendas, acompanhamento financeiro e painel administrativo.

Você pode conhecer a demonstração agora mesmo na visão do cliente acessando:

🌐 www.pedeja.dev.br

Caso tenha interesse em conhecer todas as funcionalidades e a área administrativa, podemos agendar uma apresentação rápida e mostrar a plataforma em funcionamento.

Fico à disposição."""

# ── Style Sheet ────────────────────────────────────────────────────────────────
STYLE = """
/* ══════════════════════════════════════════
   PedeJá Prospector  –  Modern Dark Theme
   ══════════════════════════════════════════ */

QMainWindow, QDialog {
    background-color: #070D1F;
}
QWidget {
    background-color: transparent;
    color: #E2E8F0;
    font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
    font-size: 13px;
}

/* ── Tabs ─────────────────────────────── */
QTabWidget::pane {
    border: 1.5px solid #1A2540;
    border-radius: 0 16px 16px 16px;
    background: #0C1628;
    top: -1.5px;
}
QTabBar::tab {
    background: transparent;
    color: #3B5280;
    padding: 12px 26px;
    border: none;
    border-bottom: 2.5px solid transparent;
    font-weight: 600;
    font-size: 13px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    color: #60A5FA;
    border-bottom: 2.5px solid #3B82F6;
}
QTabBar::tab:hover:!selected {
    color: #64748B;
    background: rgba(59,130,246,0.05);
    border-radius: 6px 6px 0 0;
}

/* ── Inputs ───────────────────────────── */
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background: #080F1E;
    border: 1.5px solid #1E2D4A;
    border-radius: 10px;
    padding: 10px 14px;
    color: #F1F5F9;
    selection-background-color: #2563EB;
    selection-color: white;
    font-size: 13px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {
    border-color: #3B82F6;
}
QLineEdit:hover:!focus, QComboBox:hover:!focus, QSpinBox:hover:!focus {
    border-color: #2A3F63;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #4A5A7A;
    margin-right: 8px;
}
QComboBox QAbstractItemView {
    background: #0E1829;
    border: 1.5px solid #1E2D4A;
    border-radius: 10px;
    selection-background-color: #1D3461;
    color: #E2E8F0;
    padding: 4px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    padding: 8px 12px;
    border-radius: 6px;
    min-height: 26px;
}
QComboBox QAbstractItemView::item:hover {
    background: #1A2A45;
}
QSpinBox::up-button, QSpinBox::down-button {
    background: #141F35;
    border: none;
    width: 20px;
    border-radius: 4px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background: #2563EB;
}
QSpinBox::up-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #94A3B8;
}
QSpinBox::down-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #94A3B8;
}

/* ── Buttons ──────────────────────────── */
QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #3B82F6, stop:1 #2563EB);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 11px 20px;
    font-weight: 700;
    font-size: 13px;
    letter-spacing: 0.2px;
    min-height: 38px;
}
QPushButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #60A5FA, stop:1 #3B82F6);
}
QPushButton:pressed {
    background: #1D4ED8;
}
QPushButton:disabled {
    background: #111D33;
    color: #2D3F60;
    border: 1.5px solid #1A2540;
}
QPushButton#secondary {
    background: #0E1829;
    color: #64748B;
    border: 1.5px solid #1E2D4A;
    font-weight: 600;
}
QPushButton#secondary:hover {
    background: #141F35;
    color: #94A3B8;
    border-color: #2563EB;
}
QPushButton#secondary:pressed {
    background: #080F1E;
}
QPushButton#success {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #34D399, stop:1 #10B981);
    color: #022C22;
    font-weight: 700;
}
QPushButton#success:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #6EE7B7, stop:1 #34D399);
}
QPushButton#success:disabled {
    background: #0C2218;
    color: #1A4433;
    border: 1.5px solid #0C2218;
}
QPushButton#whatsapp {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #25D366, stop:1 #128C7E);
    color: white;
    font-weight: 700;
}
QPushButton#whatsapp:hover {
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #57F290, stop:1 #25D366);
}
QPushButton#icon_btn {
    background: #0E1829;
    color: #64748B;
    border: 1.5px solid #1A2540;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 15px;
    min-height: 38px;
    min-width: 38px;
    max-width: 38px;
    font-weight: 400;
}
QPushButton#icon_btn:hover {
    background: #141F35;
    color: #94A3B8;
}
QPushButton#danger {
    background: #2D0F0F;
    color: #F87171;
    border: 1.5px solid #7F1D1D;
    font-weight: 600;
}
QPushButton#danger:hover {
    background: #3D1515;
    border-color: #DC2626;
}

/* ── Table ────────────────────────────── */
QTableWidget {
    background: #060C1A;
    border: 1.5px solid #1A2540;
    border-radius: 14px;
    gridline-color: #0C1628;
    color: #CBD5E1;
    font-size: 12.5px;
    alternate-background-color: #090E1C;
}
QTableWidget::item {
    padding: 9px 12px;
    border: none;
}
QTableWidget::item:hover {
    background: #101D33;
}
QTableWidget::item:selected {
    background: #1B3363;
    color: #93C5FD;
}
QHeaderView {
    background: #060C1A;
}
QHeaderView::section {
    background: #060C1A;
    color: #334D7A;
    padding: 11px 12px;
    border: none;
    border-bottom: 1.5px solid #1A2540;
    border-right: 1px solid #0D1929;
    font-weight: 700;
    font-size: 10.5px;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}
QHeaderView::section:last {
    border-right: none;
}
QHeaderView::section:hover {
    background: #0D1929;
    color: #4A6A9A;
}

/* ── Progress ─────────────────────────── */
QProgressBar {
    border: none;
    border-radius: 4px;
    background: #080F1E;
    height: 6px;
    text-align: center;
    color: transparent;
    font-size: 1px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 #2563EB, stop:0.5 #6D28D9, stop:1 #7C3AED);
    border-radius: 4px;
}

/* ── Scrollbars ───────────────────────── */
QScrollBar:vertical {
    background: #060C1A;
    width: 6px;
    border-radius: 3px;
    margin: 2px 0;
}
QScrollBar::handle:vertical {
    background: #1E2D4A;
    border-radius: 3px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #2D4A7A; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #060C1A;
    height: 6px;
    border-radius: 3px;
}
QScrollBar::handle:horizontal {
    background: #1E2D4A;
    border-radius: 3px;
}
QScrollBar::handle:horizontal:hover { background: #2D4A7A; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Cards & Frames ───────────────────── */
QFrame#card {
    background: #0C1628;
    border: 1.5px solid #1A2540;
    border-radius: 16px;
}
QFrame#header_frame {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #09122A, stop:0.6 #0A1525, stop:1 #0C1030);
    border: 1.5px solid #1A2540;
    border-radius: 18px;
}
QFrame#status_frame {
    background: #080F1E;
    border: 1px solid #1A2540;
    border-radius: 10px;
}
QFrame#step_card {
    background: #0D1929;
    border: 1px solid #1A2540;
    border-radius: 14px;
}

/* ── Labels ───────────────────────────── */
QLabel#app_title {
    font-size: 22px;
    font-weight: 800;
    color: #F1F5F9;
    letter-spacing: -0.3px;
}
QLabel#app_subtitle {
    font-size: 12px;
    color: #3B5280;
}
QLabel#section {
    font-size: 13px;
    font-weight: 700;
    color: #64748B;
    letter-spacing: 0.5px;
}
QLabel#field_label {
    font-size: 10.5px;
    font-weight: 700;
    color: #334D7A;
    letter-spacing: 1px;
}
QLabel#badge_blue {
    background: #1B3363;
    color: #93C5FD;
    border-radius: 10px;
    padding: 2px 12px;
    font-size: 11.5px;
    font-weight: 700;
}
QLabel#badge_green {
    background: #052E1E;
    color: #34D399;
    border-radius: 10px;
    padding: 2px 12px;
    font-size: 11.5px;
    font-weight: 700;
}
QLabel#tip {
    font-size: 12px;
    color: #3B5280;
    padding: 10px 16px;
    background: #080F1E;
    border-radius: 10px;
    border-left: 3px solid #2563EB;
}
QLabel#step_num {
    color: white;
    border-radius: 14px;
    font-size: 13px;
    font-weight: 800;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
    qproperty-alignment: AlignCenter;
}
QLabel#version_tag {
    background: #0E1829;
    color: #2D4A7A;
    border: 1px solid #1A2540;
    border-radius: 6px;
    padding: 1px 8px;
    font-size: 10.5px;
    font-weight: 700;
}

/* ── Splitter ─────────────────────────── */
QSplitter::handle {
    background: #1A2540;
    width: 1px;
    margin: 12px 0;
}

/* ── Status Bar ───────────────────────── */
QStatusBar {
    background: #070D1F;
    color: #2D3F60;
    border-top: 1px solid #111D33;
    font-size: 11.5px;
    padding: 0 8px;
}
QStatusBar::item { border: none; }

/* ── Message Box ──────────────────────── */
QMessageBox {
    background: #0E1829;
}
QMessageBox QLabel {
    color: #CBD5E1;
    background: transparent;
}
QMessageBox QPushButton {
    min-width: 80px;
}
"""


# ── Data Model ─────────────────────────────────────────────────────────────────
@dataclass
class Lead:
    nome: str
    endereco: str = ""
    telefone: str = ""
    site: str = ""
    maps_url: str = ""
    cidade: str = ""
    estado: str = ""
    segmento: str = ""
    place_id: str = ""


# ── Config & DB ────────────────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_config(data: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT, endereco TEXT, telefone TEXT, site TEXT,
            maps_url TEXT, cidade TEXT, estado TEXT, segmento TEXT,
            place_id TEXT UNIQUE, created_at TEXT
        )"""
    )
    conn.commit()
    conn.close()


def save_leads(leads: list[Lead]) -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for lead in leads:
        cur.execute(
            """INSERT OR IGNORE INTO leads
               (nome,endereco,telefone,site,maps_url,cidade,estado,segmento,place_id,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                lead.nome, lead.endereco, lead.telefone, lead.site,
                lead.maps_url, lead.cidade, lead.estado, lead.segmento,
                lead.place_id, datetime.now().isoformat(timespec="seconds"),
            ),
        )
    conn.commit()
    conn.close()


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("55"):
        return digits
    if len(digits) in (10, 11):
        return "55" + digits
    return digits


# ── Logo ───────────────────────────────────────────────────────────────────────
def make_logo_pixmap(size: int = 48) -> QPixmap:
    svg_path = ASSETS_DIR / "logo.svg"
    if svg_path.exists():
        try:
            from PySide6.QtSvg import QSvgRenderer
            pix = QPixmap(size, size)
            pix.fill(Qt.transparent)
            renderer = QSvgRenderer(str(svg_path))
            p = QPainter(pix)
            p.setRenderHint(QPainter.Antialiasing)
            renderer.render(p, QRectF(0, 0, size, size))
            p.end()
            return pix
        except ImportError:
            pass

    # Fallback: painted gradient square with "PJ"
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0.0, QColor("#2563EB"))
    grad.setColorAt(1.0, QColor("#7C3AED"))
    p.setBrush(QBrush(grad))
    p.setPen(Qt.NoPen)
    r = size * 0.22
    p.drawRoundedRect(0, 0, size, size, r, r)
    p.setPen(QColor("white"))
    f = QFont("Segoe UI", int(size * 0.30), QFont.Bold)
    p.setFont(f)
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, "PJ")
    p.end()
    return pix


# ── Search Worker ──────────────────────────────────────────────────────────────
class SearchWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, api_key: str, segmento: str, estado: str, cidade: str, max_results: int):
        super().__init__()
        self.api_key = api_key
        self.segmento = segmento
        self.estado = estado
        self.cidade = cidade
        self.max_results = max_results

    def run(self):
        try:
            leads: list[Lead] = []
            query = f"{self.segmento} em {self.cidade} {self.estado} Brasil"
            base_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params: dict = {"query": query, "key": self.api_key, "language": "pt-BR", "region": "br"}
            next_page_token: str | None = None

            while len(leads) < self.max_results:
                if next_page_token:
                    time.sleep(2.2)
                    params = {"pagetoken": next_page_token, "key": self.api_key,
                              "language": "pt-BR", "region": "br"}

                pct = min(90, int(len(leads) / max(1, self.max_results) * 100))
                self.progress.emit(pct, "Buscando estabelecimentos...")
                resp = requests.get(base_url, params=params, timeout=25)
                data = resp.json()
                status = data.get("status")
                if status not in ("OK", "ZERO_RESULTS"):
                    msg = data.get("error_message") or status or "Erro desconhecido na API"
                    raise RuntimeError(msg)
                if status == "ZERO_RESULTS":
                    break

                for item in data.get("results", []):
                    if len(leads) >= self.max_results:
                        break
                    place_id = item.get("place_id", "")
                    details = self._get_details(place_id)
                    lead = Lead(
                        nome=details.get("name") or item.get("name", ""),
                        endereco=details.get("formatted_address") or item.get("formatted_address", ""),
                        telefone=details.get("formatted_phone_number", ""),
                        site=details.get("website", ""),
                        maps_url=details.get("url", ""),
                        cidade=self.cidade,
                        estado=self.estado,
                        segmento=self.segmento,
                        place_id=place_id,
                    )
                    leads.append(lead)
                    pct2 = min(95, int(len(leads) / max(1, self.max_results) * 100))
                    self.progress.emit(pct2, f"Coletando: {lead.nome}")

                next_page_token = data.get("next_page_token")
                if not next_page_token:
                    break

            self.progress.emit(100, "Busca concluída.")
            self.finished.emit(leads)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _get_details(self, place_id: str) -> dict:
        if not place_id:
            return {}
        fields = "name,formatted_address,formatted_phone_number,website,url"
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {"place_id": place_id, "fields": fields, "key": self.api_key, "language": "pt-BR"}
        try:
            data = requests.get(url, params=params, timeout=25).json()
            if data.get("status") != "OK":
                return {}
            return data.get("result", {})
        except Exception:
            return {}


# ── Profile Messages ───────────────────────────────────────────────────────────
PROFILE_MSGS = {
    "sem": (
        "📵  Sem cardápio digital",
        "Oi {nome}! Tudo bem?\n\n"
        "Vi que o *{restaurante}* ainda não tem cardápio digital. "
        "Montei como ficaria — dá uma olhada aqui: www.pedeja.dev.br\n\n"
        "Se gostar, posso mostrar a parte administrativa numa conversa rápida. O que acha?"
    ),
    "basico": (
        "📱  Tem cardápio básico",
        "Oi {nome}! Tudo bem?\n\n"
        "Vi que o *{restaurante}* já tem presença digital — ótimo sinal. "
        "O PedeJá pode evoluir isso com pedidos organizados pelo WhatsApp, "
        "controle financeiro e programa de fidelidade integrado.\n\n"
        "Vale uma olhada? www.pedeja.dev.br"
    ),
    "completo": (
        "💻  Tem sistema completo",
        "Oi {nome}! Tudo bem?\n\n"
        "Vi que o *{restaurante}* já usa cardápio digital — ótimo. "
        "O PedeJá tem alguns diferenciais que talvez complementem o que você usa: "
        "programa de fidelidade, impressão automática de pedidos e painel financeiro integrado.\n\n"
        "Vale comparar rapidinho? www.pedeja.dev.br"
    ),
}


class ProfileDialog(QDialog):
    """Diálogo de seleção de perfil antes de abrir o WhatsApp."""

    def __init__(self, nome: str, phone: str, parent=None):
        super().__init__(parent)
        self.nome  = nome
        self.phone = phone
        self.setWindowTitle("Selecionar perfil")
        self.setFixedWidth(460)
        self.setModal(True)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Como é o estabelecimento?")
        title.setStyleSheet("font-size:16px;font-weight:800;color:#F1F5F9;")
        sub = QLabel("Escolha o perfil para enviar a mensagem certa")
        sub.setStyleSheet("font-size:12px;color:#64748B;")
        layout.addWidget(title)
        layout.addWidget(sub)

        # Nome do contato
        nome_lbl = QLabel("NOME DO CONTATO")
        nome_lbl.setObjectName("field_label")
        self.nome_input = QLineEdit(self.nome)
        self.nome_input.setPlaceholderText("Ex: João, Maria, pessoal…")
        self.nome_input.setFixedHeight(38)
        layout.addWidget(nome_lbl)
        layout.addWidget(self.nome_input)

        layout.addSpacing(4)

        # Profile buttons
        for key, (label, _) in PROFILE_MSGS.items():
            btn = QPushButton(label)
            btn.setObjectName("secondary")
            btn.setFixedHeight(48)
            btn.setStyleSheet(
                "QPushButton#secondary{text-align:left;padding-left:16px;"
                "font-size:14px;font-weight:700;border-radius:12px;}"
                "QPushButton#secondary:hover{border-color:#3B82F6;color:#93C5FD;}"
            )
            btn.clicked.connect(lambda checked, k=key: self._send(k))
            layout.addWidget(btn)

        cancel = QPushButton("Cancelar")
        cancel.setObjectName("secondary")
        cancel.setFixedHeight(38)
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

    def _send(self, profile: str):
        nome = self.nome_input.text().strip() or "pessoal"
        restaurante = self.nome
        _, tmpl = PROFILE_MSGS[profile]
        msg = tmpl.replace("{nome}", nome).replace("{restaurante}", restaurante)
        url = f"https://wa.me/{self.phone}?text={urllib.parse.quote(msg)}"
        webbrowser.open(url)
        self.accept()


# ── Main Window ────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self.config = load_config()
        self.leads: list[Lead] = []
        self.worker: SearchWorker | None = None
        self._api_visible = False

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setWindowIcon(QIcon(make_logo_pixmap(32)))
        self.resize(1280, 800)
        self.setMinimumSize(900, 600)

        self._build_ui()
        self._build_statusbar()

    # ── UI Layout ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root_widget")
        root.setStyleSheet("QWidget#root_widget { background-color: #070D1F; }")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        layout.addWidget(self._build_header())

        tabs = QTabWidget()
        tabs.addTab(self._build_search_tab(), "  🔍  Buscar Leads  ")
        tabs.addTab(self._build_message_tab(), "  💬  Mensagem & WhatsApp  ")
        tabs.addTab(self._build_help_tab(), "  ❓  Ajuda  ")
        layout.addWidget(tabs, 1)

        self.setCentralWidget(root)

    def _build_statusbar(self):
        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.status_bar_label = QLabel("Pronto.")
        sb.addWidget(self.status_bar_label, 1)
        version_lbl = QLabel(f"v{APP_VERSION}")
        version_lbl.setObjectName("version_tag")
        sb.addPermanentWidget(version_lbl)
        self.setStatusBar(sb)

    def _build_header(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("header_frame")
        frame.setFixedHeight(88)
        row = QHBoxLayout(frame)
        row.setContentsMargins(22, 0, 22, 0)
        row.setSpacing(16)

        # Logo
        logo_lbl = QLabel()
        logo_lbl.setPixmap(make_logo_pixmap(52))
        logo_lbl.setFixedSize(52, 52)
        row.addWidget(logo_lbl)

        # Title block
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_lbl = QLabel("PedeJá Prospector")
        title_lbl.setObjectName("app_title")
        sub_lbl = QLabel("Busque estabelecimentos, exporte leads e abra o WhatsApp com mensagem pronta.")
        sub_lbl.setObjectName("app_subtitle")
        title_col.addWidget(title_lbl)
        title_col.addWidget(sub_lbl)
        row.addLayout(title_col)
        row.addStretch()

        # API Key input group
        api_col = QVBoxLayout()
        api_col.setSpacing(6)
        api_lbl = QLabel("GOOGLE PLACES API KEY")
        api_lbl.setObjectName("field_label")
        api_row = QHBoxLayout()
        api_row.setSpacing(6)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Cole sua chave aqui…")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.api_key_input.setMinimumWidth(300)
        self.api_key_input.setFixedHeight(38)

        self._eye_btn = QPushButton("👁")
        self._eye_btn.setObjectName("icon_btn")
        self._eye_btn.setToolTip("Mostrar / ocultar chave")
        self._eye_btn.clicked.connect(self._toggle_api_visibility)

        save_btn = QPushButton("Salvar")
        save_btn.setObjectName("secondary")
        save_btn.setFixedHeight(38)
        save_btn.clicked.connect(self._save_api_key)

        api_row.addWidget(self.api_key_input)
        api_row.addWidget(self._eye_btn)
        api_row.addWidget(save_btn)
        api_col.addWidget(api_lbl)
        api_col.addLayout(api_row)
        row.addLayout(api_col)

        return frame

    # ── Search Tab ─────────────────────────────────────────────────────────────

    def _build_search_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Form card ──
        card = QFrame()
        card.setObjectName("card")
        form = QGridLayout(card)
        form.setContentsMargins(20, 18, 20, 18)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        def field_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("field_label")
            return lbl

        self.segment_input = QLineEdit("lanchonete")
        self.segment_input.setFixedHeight(38)

        self.estado_combo = QComboBox()
        self.estado_combo.addItems(sorted(ESTADOS_CIDADES.keys()))
        self.estado_combo.setCurrentText("SP")
        self.estado_combo.setFixedHeight(38)
        self.estado_combo.currentTextChanged.connect(self._refresh_cidades)

        # Cidade: combo editável com autocomplete (suporta 5.000+ cidades)
        self.cidade_combo = QComboBox()
        self.cidade_combo.setEditable(True)
        self.cidade_combo.setInsertPolicy(QComboBox.NoInsert)
        self.cidade_combo.setFixedHeight(38)
        self.cidade_combo.lineEdit().setPlaceholderText("Digite para filtrar…")
        self._cidade_completer = None
        self._refresh_cidades()

        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 60)
        self.max_spin.setValue(20)
        self.max_spin.setFixedHeight(38)
        self.max_spin.setFixedWidth(80)

        self.search_btn = QPushButton("  🔍  Pesquisar")
        self.search_btn.setFixedHeight(38)
        self.search_btn.clicked.connect(self._start_search)

        self.clear_btn = QPushButton("Limpar")
        self.clear_btn.setObjectName("danger")
        self.clear_btn.setFixedHeight(38)
        self.clear_btn.clicked.connect(self._clear_results)

        export_xlsx_btn = QPushButton("  📊  Excel")
        export_xlsx_btn.setObjectName("success")
        export_xlsx_btn.setFixedHeight(38)
        export_xlsx_btn.clicked.connect(self._export_xlsx)

        export_csv_btn = QPushButton("  📄  CSV")
        export_csv_btn.setObjectName("secondary")
        export_csv_btn.setFixedHeight(38)
        export_csv_btn.clicked.connect(self._export_csv)

        form.addWidget(field_label("O QUE PROCURAR"), 0, 0)
        form.addWidget(field_label("ESTADO"), 0, 1)
        form.addWidget(field_label("CIDADE"), 0, 2)
        form.addWidget(field_label("MÁX."), 0, 3)

        form.addWidget(self.segment_input, 1, 0)
        form.addWidget(self.estado_combo,  1, 1)
        form.addWidget(self.cidade_combo,  1, 2)
        form.addWidget(self.max_spin,      1, 3)
        form.addWidget(self.search_btn,    1, 4)
        form.addWidget(export_xlsx_btn,    1, 5)
        form.addWidget(export_csv_btn,     1, 6)
        form.addWidget(self.clear_btn,     1, 7)

        form.setColumnStretch(0, 3)
        form.setColumnStretch(1, 1)
        form.setColumnStretch(2, 2)
        layout.addWidget(card)

        # ── Status area ──
        status_frame = QFrame()
        status_frame.setObjectName("status_frame")
        status_frame.setFixedHeight(46)
        status_row = QHBoxLayout(status_frame)
        status_row.setContentsMargins(14, 0, 14, 0)
        status_row.setSpacing(12)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setMinimumWidth(160)
        self.progress_bar.setMaximumWidth(220)

        self.status_lbl = QLabel("Pronto para pesquisar.")
        self.status_lbl.setObjectName("app_subtitle")

        self.lead_count_badge = QLabel("0 leads")
        self.lead_count_badge.setObjectName("badge_blue")

        status_row.addWidget(self.progress_bar)
        status_row.addWidget(self.status_lbl, 1)
        status_row.addWidget(self.lead_count_badge)
        layout.addWidget(status_frame)

        # ── Table ──
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Nome", "Telefone", "Endereço", "Site", "Maps", "Cidade", "Segmento"]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._sync_selected_to_message)
        layout.addWidget(self.table, 1)
        return page

    # ── Message Tab ────────────────────────────────────────────────────────────

    def _build_message_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)

        # Left: contact
        left = QFrame()
        left.setObjectName("card")
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(22, 20, 22, 20)
        left_lay.setSpacing(10)

        sec = QLabel("CONTATO")
        sec.setObjectName("section")
        left_lay.addWidget(sec)

        nome_lbl = QLabel("NOME DO ESTABELECIMENTO")
        nome_lbl.setObjectName("field_label")
        self.nome_msg = QLineEdit()
        self.nome_msg.setPlaceholderText("Ex: Lanchonete do João")
        self.nome_msg.setFixedHeight(38)
        left_lay.addWidget(nome_lbl)
        left_lay.addWidget(self.nome_msg)

        phone_lbl = QLabel("TELEFONE / WHATSAPP")
        phone_lbl.setObjectName("field_label")
        phone_row = QHBoxLayout()
        phone_row.setSpacing(6)
        self.phone_msg = QLineEdit()
        self.phone_msg.setPlaceholderText("Ex: 19999999999")
        self.phone_msg.setFixedHeight(38)
        copy_phone_btn = QPushButton("📋")
        copy_phone_btn.setObjectName("icon_btn")
        copy_phone_btn.setToolTip("Copiar telefone")
        copy_phone_btn.clicked.connect(self._copy_phone)
        phone_row.addWidget(self.phone_msg)
        phone_row.addWidget(copy_phone_btn)
        left_lay.addWidget(phone_lbl)
        left_lay.addLayout(phone_row)

        left_lay.addSpacing(8)

        wa_btn = QPushButton("  📲  Abrir WhatsApp com mensagem")
        wa_btn.setObjectName("whatsapp")
        wa_btn.setFixedHeight(44)
        wa_btn.clicked.connect(self._open_whatsapp)
        left_lay.addWidget(wa_btn)

        tip = QLabel(
            "💡  Selecione uma linha na aba Buscar para\n"
            "preencher nome e telefone automaticamente."
        )
        tip.setObjectName("tip")
        tip.setWordWrap(True)
        left_lay.addSpacing(8)
        left_lay.addWidget(tip)
        left_lay.addStretch()

        # Right: message editor
        right = QFrame()
        right.setObjectName("card")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(22, 20, 22, 20)
        right_lay.setSpacing(10)

        msg_sec = QLabel("MENSAGEM PADRÃO")
        msg_sec.setObjectName("section")
        right_lay.addWidget(msg_sec)

        self.message_editor = QPlainTextEdit()
        self.message_editor.setPlainText(self.config.get("message", DEFAULT_MESSAGE))
        right_lay.addWidget(self.message_editor, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        save_msg_btn = QPushButton("💾  Salvar")
        save_msg_btn.setObjectName("secondary")
        save_msg_btn.setFixedHeight(36)
        save_msg_btn.clicked.connect(self._save_message)
        reset_msg_btn = QPushButton("↺  Restaurar padrão")
        reset_msg_btn.setObjectName("secondary")
        reset_msg_btn.setFixedHeight(36)
        reset_msg_btn.clicked.connect(lambda: self.message_editor.setPlainText(DEFAULT_MESSAGE))
        btn_row.addWidget(save_msg_btn)
        btn_row.addWidget(reset_msg_btn)
        btn_row.addStretch()
        right_lay.addLayout(btn_row)

        vars_tip = QLabel("Variáveis disponíveis:  {nome}  ·  {cidade}  ·  {segmento}")
        vars_tip.setObjectName("tip")
        right_lay.addWidget(vars_tip)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([360, 800])
        layout.addWidget(splitter, 1)
        return page

    # ── Help Tab ───────────────────────────────────────────────────────────────

    def _build_help_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        sec = QLabel("COMO USAR")
        sec.setObjectName("section")
        layout.addWidget(sec)

        steps = [
            ("1", "#2563EB", "Configure sua API Key",
             "Informe sua Google Places API Key no campo do cabeçalho e clique em Salvar. "
             "A chave é armazenada localmente no seu perfil."),
            ("2", "#7C3AED", "Busque estabelecimentos",
             "Na aba Buscar Leads, informe o segmento (ex: pizzaria, lanchonete), "
             "escolha o estado e a cidade, defina o número máximo de resultados e clique em Pesquisar."),
            ("3", "#0891B2", "Exporte os leads",
             "Após a busca, exporte os resultados para Excel (.xlsx) ou CSV para usar em outras ferramentas."),
            ("4", "#059669", "Envie via WhatsApp",
             "Selecione uma linha na tabela de leads e vá até a aba Mensagem & WhatsApp. "
             "Edite a mensagem se necessário e clique em Abrir WhatsApp — o envio é sempre manual."),
        ]

        for num, color, title, desc in steps:
            card = QFrame()
            card.setObjectName("step_card")
            row = QHBoxLayout(card)
            row.setContentsMargins(18, 16, 18, 16)
            row.setSpacing(16)

            num_lbl = QLabel(num)
            num_lbl.setObjectName("step_num")
            num_lbl.setFixedSize(28, 28)
            num_lbl.setAlignment(Qt.AlignCenter)
            num_lbl.setStyleSheet(
                f"QLabel#step_num {{ background: {color}; color: white; "
                f"border-radius: 14px; font-size: 13px; font-weight: 800; }}"
            )

            text_col = QVBoxLayout()
            text_col.setSpacing(4)
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("font-weight: 700; font-size: 13px; color: #CBD5E1;")
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("font-size: 12px; color: #3B5280;")
            desc_lbl.setWordWrap(True)
            text_col.addWidget(title_lbl)
            text_col.addWidget(desc_lbl)

            row.addWidget(num_lbl)
            row.addLayout(text_col, 1)
            layout.addWidget(card)

        warn = QLabel(
            "⚠️  Use contatos públicos com responsabilidade. "
            "Evite disparos em massa e respeite a LGPD."
        )
        warn.setObjectName("tip")
        warn.setStyleSheet(
            "QLabel { font-size: 12px; color: #B45309; padding: 10px 16px; "
            "background: #1C1100; border-radius: 10px; border-left: 3px solid #D97706; }"
        )
        warn.setWordWrap(True)
        layout.addWidget(warn)
        layout.addStretch()
        return page

    # ── Actions ────────────────────────────────────────────────────────────────

    def _toggle_api_visibility(self):
        self._api_visible = not self._api_visible
        self.api_key_input.setEchoMode(
            QLineEdit.Normal if self._api_visible else QLineEdit.Password
        )

    def _save_api_key(self):
        self.config["api_key"] = self.api_key_input.text().strip()
        save_config(self.config)
        self._set_status("✓  Chave API salva com sucesso.")

    def _save_message(self):
        self.config["message"] = self.message_editor.toPlainText()
        save_config(self.config)
        self._set_status("✓  Mensagem salva.")

    def _refresh_cidades(self):
        if not hasattr(self, "cidade_combo"):
            return
        from PySide6.QtWidgets import QCompleter
        from PySide6.QtCore import Qt as _Qt

        estado = self.estado_combo.currentText()
        cidades = ESTADOS_CIDADES.get(estado, [])

        self.cidade_combo.blockSignals(True)
        self.cidade_combo.clear()
        self.cidade_combo.addItems(cidades)

        # Autocomplete com busca parcial em qualquer posição
        completer = QCompleter(cidades, self.cidade_combo)
        completer.setCaseSensitivity(_Qt.CaseInsensitive)
        completer.setFilterMode(_Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.cidade_combo.setCompleter(completer)

        if cidades:
            self.cidade_combo.setCurrentIndex(0)
        self.cidade_combo.blockSignals(False)

    def _start_search(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, APP_NAME, "Informe sua Google Places API Key antes de pesquisar.")
            return
        segmento = self.segment_input.text().strip()
        if not segmento:
            QMessageBox.warning(self, APP_NAME, "Informe o que deseja procurar.\nEx: lanchonete, pizzaria…")
            return

        self.config["api_key"] = api_key
        save_config(self.config)

        self.search_btn.setEnabled(False)
        self.search_btn.setText("  ⏳  Pesquisando…")
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Iniciando busca…")
        self.lead_count_badge.setText("— leads")

        self.worker = SearchWorker(
            api_key, segmento,
            self.estado_combo.currentText(),
            self.cidade_combo.currentText(),
            self.max_spin.value(),
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_progress(self, value: int, message: str):
        self.progress_bar.setValue(value)
        self.status_lbl.setText(message)

    def _on_finished(self, leads: list[Lead]):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("  🔍  Pesquisar")
        self.leads = leads
        save_leads(leads)
        self._populate_table()
        count = len(leads)
        self.lead_count_badge.setText(f"{count} lead{'s' if count != 1 else ''}")
        self.lead_count_badge.setObjectName("badge_green" if count else "badge_blue")
        self.lead_count_badge.setStyleSheet("")  # force style refresh
        self.status_lbl.setText(f"Busca concluída — {count} estabelecimento(s) encontrado(s).")
        self._set_status(f"✓  {count} lead(s) carregado(s) com sucesso.")

    def _on_failed(self, error: str):
        self.search_btn.setEnabled(True)
        self.search_btn.setText("  🔍  Pesquisar")
        self.progress_bar.setValue(0)
        self.status_lbl.setText("Erro na busca.")
        self._set_status(f"✗  Erro: {error[:80]}")
        QMessageBox.critical(
            self, APP_NAME,
            f"Não foi possível concluir a busca:\n\n{error}\n\n"
            "Verifique sua API Key e conexão com a internet.",
        )

    def _populate_table(self):
        self.table.setRowCount(0)
        for lead in self.leads:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = [
                lead.nome, lead.telefone, lead.endereco,
                lead.site, lead.maps_url,
                f"{lead.cidade} / {lead.estado}", lead.segmento,
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val or "")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, item)
        self.table.resizeRowsToContents()

    def _clear_results(self):
        if not self.leads:
            return
        if QMessageBox.question(
            self, APP_NAME, "Limpar todos os resultados da tabela?",
            QMessageBox.Yes | QMessageBox.No,
        ) == QMessageBox.Yes:
            self.leads = []
            self.table.setRowCount(0)
            self.progress_bar.setValue(0)
            self.status_lbl.setText("Pronto para pesquisar.")
            self.lead_count_badge.setText("0 leads")
            self._set_status("Resultados limpos.")

    def _leads_as_dicts(self) -> list[dict]:
        return [lead.__dict__ for lead in self.leads]

    def _export_xlsx(self):
        if not self.leads:
            QMessageBox.warning(self, APP_NAME, "Nenhum lead para exportar. Faça uma busca primeiro.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar Excel", "leads_pedeja.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        pd.DataFrame(self._leads_as_dicts()).to_excel(path, index=False)
        self._set_status(f"✓  Excel exportado: {path}")
        QMessageBox.information(self, APP_NAME, f"Excel exportado com sucesso!\n\n{path}")

    def _export_csv(self):
        if not self.leads:
            QMessageBox.warning(self, APP_NAME, "Nenhum lead para exportar. Faça uma busca primeiro.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Salvar CSV", "leads_pedeja.csv", "CSV (*.csv)")
        if not path:
            return
        dicts = self._leads_as_dicts()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(dicts[0].keys()), delimiter=";")
            writer.writeheader()
            writer.writerows(dicts)
        self._set_status(f"✓  CSV exportado: {path}")
        QMessageBox.information(self, APP_NAME, f"CSV exportado com sucesso!\n\n{path}")

    def _sync_selected_to_message(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if row < len(self.leads):
            lead = self.leads[row]
            self.nome_msg.setText(lead.nome)
            self.phone_msg.setText(lead.telefone)

    def _copy_phone(self):
        phone = self.phone_msg.text().strip()
        if phone:
            QApplication.clipboard().setText(phone)
            self._set_status(f"Telefone copiado: {phone}")

    def _open_whatsapp(self):
        phone = normalize_phone(self.phone_msg.text())
        if not phone:
            QMessageBox.warning(self, APP_NAME, "Informe um telefone válido antes de abrir o WhatsApp.")
            return
        nome = self.nome_msg.text().strip() or ""
        dlg = ProfileDialog(nome, phone, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._set_status(f"WhatsApp aberto para {phone}.")

    def _set_status(self, text: str):
        self.status_bar_label.setText(text)


# ── Entry Point ────────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
