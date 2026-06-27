from __future__ import annotations

import re

SOFTWARE_PROJECT_NAME = 'MedienScoutsWebsite'
SOFTWARE_DEVELOPER_NAME = 'Tim von der Weppen'
SOFTWARE_LICENSE_TEXT = 'Projektlizenz in LICENSE.md'
DEFAULT_REPOSITORY_URL = 'https://github.com/tvdw07/MedienScoutsWebsite'
DEFAULT_LAWFUL_BASIS_TEXT = (
    'Soweit keine speziellere Rechtsgrundlage genannt wird, erfolgt die Verarbeitung auf Grundlage '
    'von Art. 6 Abs. 1 lit. b, c und f DSGVO.'
)
DEFAULT_STORAGE_DURATION_TEXT = (
    'Personenbezogene Daten werden nur so lange gespeichert, wie es für den jeweiligen Zweck erforderlich '
    'ist oder gesetzliche Aufbewahrungspflichten bestehen.'
)


def _clean(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _config_text(config, *names, default=None):
    for name in names:
        value = _clean(config.get(name))
        if value:
            return value
    return default


def _normalize_url(value):
    value = _clean(value)
    if not value:
        return None
    if '://' not in value:
        return f'https://{value}'
    return value


def _normalize_phone_href(value):
    value = _clean(value)
    if not value:
        return None
    href_value = re.sub(r'[^0-9+]', '', value)
    return f'tel:{href_value}' if href_value else None


def _address_lines(street, house_number, postal_code, city, country):
    lines = []
    street_line = ' '.join(part for part in [street, house_number] if part)
    if street_line:
        lines.append(street_line)

    city_line = ' '.join(part for part in [postal_code, city] if part)
    if city_line:
        lines.append(city_line)

    if country:
        lines.append(country)

    return lines


def _contact_item(label, value, href=None, external=False):
    value = _clean(value)
    if not value:
        return None

    return {
        'label': label,
        'value': value,
        'href': href,
        'external': external,
    }


def _ticket_category(title, summary, points):
    return {
        'title': title,
        'summary': summary,
        'points': points,
    }


def build_legal_context(config):
    operator_name = _config_text(config, 'LEGAL_OPERATOR_NAME')
    organization_name = _config_text(config, 'LEGAL_ORGANIZATION_NAME')
    representative_name = _config_text(config, 'LEGAL_REPRESENTATIVE_NAME')
    street = _config_text(config, 'LEGAL_STREET')
    house_number = _config_text(config, 'LEGAL_HOUSE_NUMBER')
    postal_code = _config_text(config, 'LEGAL_POSTAL_CODE')
    city = _config_text(config, 'LEGAL_CITY')
    country = _config_text(config, 'LEGAL_COUNTRY')
    phone = _config_text(config, 'LEGAL_PHONE')
    email = _config_text(config, 'LEGAL_EMAIL')
    website = _config_text(config, 'LEGAL_WEBSITE')
    vat_id = _config_text(config, 'LEGAL_VAT_ID')
    editorial_responsible_name = _config_text(config, 'LEGAL_EDITORIAL_RESPONSIBLE_NAME')
    editorial_responsible_email = _config_text(config, 'LEGAL_EDITORIAL_RESPONSIBLE_EMAIL')
    privacy_contact_name = _config_text(config, 'LEGAL_PRIVACY_CONTACT_NAME')
    privacy_contact_email = _config_text(config, 'LEGAL_PRIVACY_CONTACT_EMAIL')
    support_email = _config_text(config, 'LEGAL_SUPPORT_EMAIL')
    repository_url = _normalize_url(_config_text(config, 'LEGAL_GITHUB_REPOSITORY', default=DEFAULT_REPOSITORY_URL))
    version = _config_text(config, 'LEGAL_VERSION')
    build_number = _config_text(config, 'LEGAL_BUILD_NUMBER')
    lawful_basis_text = _config_text(config, 'LEGAL_LAWFUL_BASIS_TEXT', default=DEFAULT_LAWFUL_BASIS_TEXT)
    storage_duration_text = _config_text(
        config,
        'LEGAL_STORAGE_DURATION_TEXT',
        default=DEFAULT_STORAGE_DURATION_TEXT,
    )

    operator = {
        'name': operator_name,
        'organization_name': organization_name,
        'representative_name': representative_name,
        'address_lines': _address_lines(street, house_number, postal_code, city, country),
        'contact_items': [
            _contact_item('Telefon', phone, _normalize_phone_href(phone)),
            _contact_item('E-Mail', email, f'mailto:{email}' if email else None),
            _contact_item('Website', website, _normalize_url(website), external=True),
        ],
        'vat_id': vat_id,
        'editorial_responsible_name': editorial_responsible_name,
        'editorial_responsible_email': editorial_responsible_email,
    }
    operator['contact_items'] = [item for item in operator['contact_items'] if item]

    privacy_contact_items = [
        _contact_item('Ansprechperson', privacy_contact_name),
        _contact_item(
            'E-Mail',
            privacy_contact_email,
            f'mailto:{privacy_contact_email}' if privacy_contact_email else None,
        ),
    ]
    privacy_contact_items = [item for item in privacy_contact_items if item]

    privacy_data_categories = [
        _ticket_category(
            'Benutzerkonto',
            'Benutzerkonten werden für die Anmeldung, die Profilverwaltung und die Berechtigungsprüfung genutzt.',
            [
                'Benutzername, Vorname, Nachname und E-Mail-Adresse',
                'Passwort-Hash statt Klartextpasswort',
                'Rollen, Rang, Aktivstatus, Aktivierungszeitraum und letzter Login',
                'Profilbild-Datei, sofern ein Bild hochgeladen wurde',
            ],
        ),
        _ticket_category(
            'Tickets',
            'Je nach Ticketart speichert die Anwendung die Formulardaten, die zur Bearbeitung des Anliegens benötigt werden.',
            [
                'Problemtickets: Vorname, Nachname, E-Mail-Adresse, Klasse, Seriennummer, Problembeschreibung, bereits unternommene Schritte, Foto und Status',
                'Fortbildungstickets: Klassenlehrkraft, E-Mail-Adresse, Fortbildungstyp, Begründung, gewünschter Termin und Status',
                'Sonstiges: Vorname, Nachname, E-Mail-Adresse, Nachricht und Status',
                'Zeitstempel der Erstellung und der weiteren Bearbeitung',
            ],
        ),
        _ticket_category(
            'Ticketnachrichten',
            'Antworten innerhalb eines Tickets werden in der Verlaufshistorie gespeichert, damit der Bearbeitungsverlauf nachvollziehbar bleibt.',
            [
                'Tickettyp und Ticket-ID',
                'Nachrichtentext',
                'Autorentyp',
                'Zeitstempel der Erstellung',
            ],
        ),
        _ticket_category(
            'Forum-Beiträge',
            'Das Forum speichert Beiträge für den internen Austausch zwischen angemeldeten Nutzern.',
            [
                'Autorname',
                'angezeigte Rolle',
                'Beitragstext',
                'Zeitstempel',
                'Kennzeichen für gelöschte Beiträge',
            ],
        ),
        _ticket_category(
            'Anhänge',
            'Hochgeladene Dateien werden nach technischen Prüfungen im konfigurierten Upload-Verzeichnis abgelegt.',
            [
                'Ticketfotos im Format PNG, JPG oder JPEG mit maximal 1 MB',
                'Profilbilder im Verzeichnis für Benutzerprofile',
                'Generierte Dateinamen auf Basis von Datum und Name',
                'Dateipfad im jeweiligen Upload-Verzeichnis',
            ],
        ),
        _ticket_category(
            'Rollen und Berechtigungen',
            'Die Administration speichert, welche Rollen und Berechtigungs-Overrides Nutzern zugeordnet sind.',
            [
                'Zuordnungen zwischen Nutzern und Rollen',
                'Zuordnungen zwischen Rollen und Berechtigungen',
                'Direkte Allow-/Deny-Overrides für einzelne Berechtigungen',
                'Zeitpunkt der Zuweisung und optionale Begründung bei Berechtigungs-Overrides',
            ],
        ),
        _ticket_category(
            'Logdaten',
            'Die Anwendung schreibt serverseitige Protokolle für Betriebs- und Sicherheitsereignisse.',
            [
                'Start- und Konfigurationsmeldungen',
                'Login-Versuche und Passwort-Reset-Ereignisse',
                'Ticket-Einreichungen und Löschaktionen',
                'Upload-, Dateipfad- und Berechtigungswarnungen',
                'Benutzer-, Ticket- oder Dateibezeichner, soweit sie für die Fehlersuche erforderlich sind',
            ],
        ),
    ]

    processing_purposes = [
        'Authentifizierung und Sitzungskontrolle',
        'Verwaltung von Benutzerkonten, Rollen und Berechtigungen',
        'Entgegennahme, Bearbeitung und Nachverfolgung von Tickets',
        'Speicherung von Antworten, Verlaufseinträgen und Forum-Beiträgen',
        'Versand von Benachrichtigungen und Zurücksetzen von Passwörtern',
        'Betrieb, Absicherung und technische Fehleranalyse der Installation',
    ]

    third_party_points = [
        'Beim Laden der Oberfläche werden Bootstrap, Font Awesome, jQuery und Popper von jsDelivr beziehungsweise cdnjs angefordert; der jeweilige CDN-Anbieter erhält dabei technische Verbindungsdaten wie die IP-Adresse.',
        'Ausgehende E-Mails werden über den im Betrieb konfigurierten SMTP-Server versendet; dieser verarbeitet Empfängeradressen und die jeweiligen Nachrichteninhalte.',
        'Je nach Hosting-Modell verarbeitet der betreibende Server oder ein beauftragter Hosting-Dienst technische Verbindungs-, Log- und Speicherdaten.',
    ]

    security_measures = [
        'Flask-WTF-geschütztes Formularhandling mit CSRF-Token',
        'Berechtigungsprüfungen für administrative Funktionen',
        'HttpOnly- und SameSite-Session-Cookies; Secure-Flag bei entsprechender Konfiguration',
        'Prüfung von Dateityp, Dateigröße und Dateipfad bei Uploads',
        'Rate-Limiting für ausgewählte POST-Endpunkte',
        'Protokollierung sicherheitsrelevanter Ereignisse und Fehlermeldungen',
    ]

    rights_items = [
        'Auskunft',
        'Berichtigung',
        'Löschung',
        'Einschränkung der Verarbeitung',
        'Datenübertragbarkeit',
        'Widerspruch gegen Verarbeitungen auf Grundlage berechtigter Interessen',
        'Beschwerde bei der zuständigen Aufsichtsbehörde',
    ]

    software = {
        'project_name': SOFTWARE_PROJECT_NAME,
        'developer_name': SOFTWARE_DEVELOPER_NAME,
        'statement': (
            'Die Software wurde ursprünglich von Tim von der Weppen entwickelt. '
            'Der Betrieb, die Administration und die Verarbeitung personenbezogener Daten erfolgen ausschließlich '
            'durch den jeweiligen Betreiber dieser Installation.'
        ),
        'repository_url': repository_url,
        'license_text': SOFTWARE_LICENSE_TEXT,
        'support_email': support_email,
        'version': version,
        'build_number': build_number,
    }

    imprint = {
        'operator': operator,
        'address_lines': operator['address_lines'],
        'contact_items': operator['contact_items'],
        'vat_id': vat_id,
        'editorial_responsible_name': editorial_responsible_name,
        'editorial_responsible_email': editorial_responsible_email,
        'software': software,
    }

    privacy = {
        'controller': operator,
        'data_protection_contact': {
            'name': privacy_contact_name,
            'email': privacy_contact_email,
            'contact_items': privacy_contact_items,
        },
        'purpose_text': (
            'Die Anwendung unterstützt Schulen und Organisationen bei der Verwaltung von Mitgliedern, '
            'Tickets, Nachrichten, Rollen und interner Kommunikation.'
        ),
        'data_categories': privacy_data_categories,
        'processing_purposes': processing_purposes,
        'lawful_basis_text': lawful_basis_text,
        'storage_duration_text': storage_duration_text,
        'third_party_points': third_party_points,
        'hosting_text': (
            'Die Anwendung wird auf der Infrastruktur des jeweiligen Betreibers oder eines von ihm beauftragten '
            'Hosting-Dienstes betrieben. Datenbank, Uploads und Logdateien liegen auf dieser Infrastruktur.'
        ),
        'email_delivery_text': (
            'E-Mails werden über den im Betrieb konfigurierten SMTP-Server versendet. Dies betrifft insbesondere '
            'Ticket-Links, Passwort-Reset-Mails und Benachrichtigungen bei neuen Tickets oder Ticketänderungen.'
        ),
        'cookie_text': (
            'Die Anwendung nutzt ein Session-Cookie, um den angemeldeten Zustand zu verwalten. '
            'Das Cookie speichert keine Ticketinhalte oder Nachrichten. Es werden keine Analyse- oder '
            'Marketing-Cookies durch die Anwendung gesetzt.'
        ),
        'security_measures': security_measures,
        'rights_items': rights_items,
        'contact_note': 'Bei Fragen zum Datenschutz kann die unten genannte Kontaktstelle genutzt werden.',
    }

    return {
        'imprint': imprint,
        'privacy': privacy,
        'software': software,
    }
