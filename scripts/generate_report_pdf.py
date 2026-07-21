import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Images directory for the current session
IMAGE_DIR = "/home/mev/.gemini/antigravity-ide/brain/9b9c1ec7-4f94-4b39-9bf2-7712fd5981fa"
IMG_LOGIN = os.path.join(IMAGE_DIR, "login_page.png")
IMG_PLANNING = os.path.join(IMAGE_DIR, "dashboard_planning.png")
IMG_MEDICAL = os.path.join(IMAGE_DIR, "dashboard_medical.png")
IMG_AUDIT = os.path.join(IMAGE_DIR, "dashboard_audit.png")

OUTPUT_PDF = "/home/mev/Documents/ProjetP/PMW/rapport_cid.pdf"

def build_pdf():
    # Make sure output directory exists
    os.makedirs(os.path.dirname(OUTPUT_PDF), exist_ok=True)

    # Document setup - Letter size with margins
    doc = SimpleDocTemplate(
        OUTPUT_PDF,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=50,
        bottomMargin=50
    )
    
    story = []
    
    # Color Palette (Premium Medical Theme)
    c_primary = colors.HexColor('#1e3a8a')   # Deep Blue
    c_secondary = colors.HexColor('#0d9488') # Teal
    c_text = colors.HexColor('#0f172a')      # Slate Text
    c_muted = colors.HexColor('#475569')     # Muted Text
    c_bg_light = colors.HexColor('#f8fafc')  # Light BG for tables/cards
    c_border = colors.HexColor('#cbd5e1')    # Border

    # Styles Setup
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=c_primary,
        spaceAfter=4,
        alignment=0
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=c_muted,
        spaceAfter=15
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=c_primary,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=c_secondary,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=c_text,
        spaceAfter=5
    )
    
    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=c_text,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=c_text
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=c_text
    )

    # Divider line helper
    def add_divider():
        divider = Table([['']], colWidths=[532], rowHeights=[1.5])
        divider.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_secondary),
            ('TOPPADDING', (0,0), (-1, -1), 0),
            ('BOTTOMPADDING', (0,0), (-1, -1), 0),
        ]))
        story.append(divider)
        story.append(Spacer(1, 10))

    # ================= PAGE 1: INTRODUCTION & ARCHITECTURE TECHNIQUE =================
    story.append(Paragraph("PROJET CID — PLATEFORME MÉDICALE WHATSAPP", title_style))
    story.append(Paragraph("Dossier de synthèse technique et état d'avancement du prototype", subtitle_style))
    add_divider()
    
    story.append(Paragraph("1. Présentation du Projet", h1_style))
    story.append(Paragraph(
        "Le projet <b>Cid (Plateforme Médicale WhatsApp)</b> est une solution innovante destinée aux cliniques et "
        "laboratoires d'analyses médicales. Son objectif est de simplifier et de sécuriser la prise de rendez-vous ainsi que "
        "la transmission des résultats d'analyses aux patients. Pour ce faire, Cid propose un double canal d'interaction : "
        "un <b>Dashboard d'Administration Web</b> pour le personnel clinique (médecins, laborantins, secrétaires) et un "
        "<b>Chatbot WhatsApp interactif</b> pour les patients. Cette architecture évite aux patients d'avoir à télécharger "
        "une application dédiée et s'appuie sur le canal WhatsApp qu'ils possèdent déjà.",
        body_style
    ))
    
    story.append(Paragraph("2. Architecture Logicielle & Technologies Internes", h1_style))
    story.append(Paragraph(
        "L'infrastructure repose sur un ensemble de technologies modernes garantissant performance, traçabilité et sécurité :",
        body_style
    ))

    # Tech Stack Table
    tech_data = [
        [Paragraph("Composant", table_header_style), Paragraph("Technologie", table_header_style), Paragraph("Rôle dans le projet", table_header_style)],
        [
            Paragraph("<b>Backend API</b>", table_cell_bold),
            Paragraph("FastAPI (Python 3)", table_cell_style),
            Paragraph("Cerveau de l'application. Reçoit les requêtes HTTP du dashboard, expose le webhook Twilio et orchestre la logique métier.", table_cell_style)
        ],
        [
            Paragraph("<b>Base de données</b>", table_cell_bold),
            Paragraph("PostgreSQL", table_cell_style),
            Paragraph("Persistance des patients, des créneaux, des réservations de rendez-vous, des sessions de conversation et des journaux d'audit.", table_cell_style)
        ],
        [
            Paragraph("<b>Chatbot WhatsApp</b>", table_cell_bold),
            Paragraph("Twilio WhatsApp API", table_cell_style),
            Paragraph("Passerelle bidirectionnelle convertissant les messages WhatsApp des patients en requêtes webhook HTTP reçues par FastAPI.", table_cell_style)
        ],
        [
            Paragraph("<b>Exposition Web</b>", table_cell_bold),
            Paragraph("Cloudflare Tunnel", table_cell_style),
            Paragraph("Création d'un tunnel sécurisé reliant le serveur FastAPI local à une URL publique sécurisée (HTTPS) reconnue par Twilio.", table_cell_style)
        ],
        [
            Paragraph("<b>Sécurité & Chiffrement</b>", table_cell_bold),
            Paragraph("Fernet (AES-256)", table_cell_style),
            Paragraph("Chiffrement symétrique fort au repos de tous les documents médicaux (PDF/images) avant leur écriture sur disque.", table_cell_style)
        ],
        [
            Paragraph("<b>Stockage Hybride</b>", table_cell_bold),
            Paragraph("Cloudinary / Local", table_cell_style),
            Paragraph("Sauvegarde déportée sur le Cloud. Si non configuré, le système bascule automatiquement sur le stockage local temporaire.", table_cell_style)
        ],
        [
            Paragraph("<b>Authentification OTP</b>", table_cell_bold),
            Paragraph("Algorithme interne", table_cell_style),
            Paragraph("Génération de codes à 6 chiffres à validité limitée (10 min) avec blocage anti brute-force pour sécuriser l'accès aux analyses.", table_cell_style)
        ],
    ]
    
    tech_table = Table(tech_data, colWidths=[110, 120, 302])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, c_bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    
    story.append(tech_table)
    story.append(Spacer(1, 10))
    story.append(PageBreak())

    # ================= PAGE 2: FONCTIONNEMENT TECHNIQUE DU TUNNEL ET DU CHATBOT =================
    story.append(Paragraph("PROJET CID — PLATEFORME MÉDICALE WHATSAPP", title_style))
    story.append(Paragraph("Fonctionnement technique détaillé du Chatbot et de l'accès clinique", subtitle_style))
    add_divider()
    
    story.append(Paragraph("3. Tunnel d'Exposition (Cloudflare Tunnel)", h1_style))
    story.append(Paragraph(
        "Pour que l'API Twilio puisse envoyer des webhooks (notifications de nouveaux messages) à notre serveur local, "
        "une URL publique sécurisée est indispensable. Cid utilise <b>Cloudflare Tunnel</b> (configuré via <code>.cloudflared/config.yml</code>). "
        "Contrairement à ngrok, Cloudflare offre une URL fixe et sécurisée par HTTPS, éliminant le besoin de reconfigurer Twilio "
        "à chaque redémarrage. Le démon Cloudflared local écoute sur le port <code>8000</code> et achemine le trafic crypté.",
        body_style
    ))
    
    story.append(Paragraph("4. Tunnel WhatsApp & Gestion des Sessions du Bot", h1_style))
    story.append(Paragraph(
        "Le chatbot WhatsApp est géré par une machine à états finis persistante en base de données. Chaque interaction d'un patient "
        "met à jour ou consulte sa session (identifiée par son numéro de téléphone unique).",
        body_style
    ))
    story.append(Paragraph(
        "<b>Cycle de communication :</b>\n"
        "1. Le patient envoie un message WhatsApp au numéro Twilio Sandbox.\n"
        "2. Twilio convertit le message en requête POST HTTP HTTPS et l'envoie à notre route <code>/twilio/webhook</code> via le Tunnel.\n"
        "3. Le backend FastAPI extrait le numéro WhatsApp de l'expéditeur et récupère sa session en BDD.\n"
        "4. En fonction de l'état actuel de la session (<code>menu</code>, <code>choix_specialite</code>, <code>choix_medecin</code>, etc.), le bot génère une réponse contextuelle et met à jour l'état de la session.\n"
        "5. La réponse est transmise via l'API Twilio au patient.",
        body_style
    ))
    
    story.append(Paragraph("5. Accès au Dashboard & Sécurité des Fichiers", h1_style))
    story.append(Paragraph(
        "Le personnel clinique accède au dashboard d'administration via un navigateur web. "
        "La sécurité de cet accès et des données est au cœur de l'architecture :",
        body_style
    ))
    
    sec_details = [
        "<b>Authentification RBAC (Role-Based Access Control) :</b> Les utilisateurs se connectent via un formulaire moderne (page split-screen). Les sessions sont maintenues via un cookie sécurisé <code>cid_session</code>. Les accès et les menus du dashboard s'adaptent selon le rôle (Admin, Médecin, Laborantin, Staff).",
        "<b>Chiffrement des analyses :</b> Lorsqu'un laborantin importe un résultat ou remplit un formulaire de saisie manuelle, le fichier PDF généré est chiffré au repos côté serveur en utilisant l'algorithme <b>Fernet (AES-256)</b>. La clé de cryptage est définie par la variable <code>FERNET_KEY</code> dans le fichier <code>.env</code>. Le fichier chiffré est stocké sur disque (ou Cloudinary).",
        "<b>Téléchargement à la volée :</b> Lors d'un téléchargement par l'administrateur ou d'une demande par le patient (sécurisée par OTP), le serveur déchiffre le document à la volée en mémoire et le sert sous sa forme originale sans jamais l'exposer en clair dans le système de fichiers."
    ]
    for sec in sec_details:
        story.append(Paragraph(f"• {sec}", bullet_style))
        
    story.append(Spacer(1, 10))
    story.append(PageBreak())

    # ================= PAGE 3: ÉTAT D'AVANCEMENT & TESTS =================
    story.append(Paragraph("PROJET CID — PLATEFORME MÉDICALE WHATSAPP", title_style))
    story.append(Paragraph("État d'avancement, tests d'intégration et perspectives de production", subtitle_style))
    add_divider()
    
    story.append(Paragraph("6. Ce qui a été Réalisé & Validé (Ce qui marche)", h1_style))
    story.append(Paragraph(
        "L'ensemble des exigences du cahier des charges initial est pleinement fonctionnel et validé :",
        body_style
    ))
    
    done_items = [
        "<b>Gestion des résultats :</b> Importation, validation stricte (PDF/images, <5 Mo), stockage chiffré Fernet et intégration optionnelle Cloudinary.",
        "<b>Dossier Médical centralisé :</b> Visualisation de la fiche administrative, de l'historique complet des RDV et des analyses d'un patient.",
        "<b>Saisie d'analyses manuelle :</b> Formulaire dynamique (Bilan sanguin, Urine, Lipidique, Libre) et génération automatisée d'analyses PDF professionnelles chiffrées.",
        "<b>Gestion des disponibilités :</b> Planification dynamique des créneaux par médecin/spécialité. Réservation via chatbot et blocage manuel clinique.",
        "<b>Chatbot complet :</b> Parcours de prise de RDV, affichage/annulation de RDV en direct et récupération de résultats sécurisée par OTP.",
        "<b>Fiabilité technique :</b> TTL cache en mémoire pour alléger la base de données. Pattern Outbox persistant en BDD pour garantir la délivrabilité des messages WhatsApp via Twilio, assisté d'un script autonome de réexpédition (<code>retry_messages.py</code>)."
    ]
    for di in done_items:
        story.append(Paragraph(f"• {di}", bullet_style))
        
    story.append(Paragraph("7. Limites Actuelles du Prototype (Ce qui ne marche pas)", h1_style))
    story.append(Paragraph(
        "Le prototype est stable et sans bugs, mais il est soumis à des limitations liées à la phase d'évaluation :",
        body_style
    ))
    
    limits = [
        "<b>Twilio Sandbox WhatsApp :</b> En mode gratuit, les numéros des patients doivent préalablement s'associer à la Sandbox en envoyant <code>join [mot-clef]</code> au numéro Twilio. Les messages sortants sont également bridés à 50 par jour.",
        "<b>Expiration des sessions :</b> Si un patient s'arrête en plein milieu d'une prise de rendez-vous, son état de session persiste indéfiniment en base de données au lieu d'expirer."
    ]
    for lim in limits:
        story.append(Paragraph(f"• {lim}", bullet_style))

    story.append(Paragraph("8. Ce qu'il reste à faire (Recommandations de Production)", h1_style))
    story.append(Paragraph(
        "Pour industrialiser la plateforme, nous recommandons les étapes suivantes :",
        body_style
    ))
    
    todos = [
        "<b>Passer sur un compte WhatsApp Business API officiel</b> afin de lever la contrainte de la Sandbox Twilio et les limites d'envoi.",
        "<b>Mettre en place une tâche cron en arrière-plan</b> pour expirer automatiquement les sessions de conversation inactives après 30 minutes.",
        "<b>Ajouter des index PostgreSQL secondaires</b> sur les colonnes clés (numéro WhatsApp, date de rendez-vous) pour optimiser les performances lors de la montée en charge."
    ]
    for todo in todos:
        story.append(Paragraph(f"• {todo}", bullet_style))

    story.append(Paragraph("9. Couverture des Tests d'Intégration", h1_style))
    story.append(Paragraph(
        "Tous les modules font l'objet de tests automatisés validés de bout en bout (smoke tests) :<br/>"
        "• <code>admin_auth_smoke_test.py</code> : cycle de session et redirections.<br/>"
        "• <code>crud_api_smoke_test.py</code> : création et suppression de dossiers patients et d'analyses.<br/>"
        "• <code>otp_smoke_test.py</code> : validation des OTP et blocage brute-force.<br/>"
        "• <code>secure_retrieve_smoke_test.py</code> : chiffrement et déchiffrement à la volée.<br/>"
        "• <code>integration_smoke_test.py</code> : scénario complet patient, prise de RDV et récupération d'analyses.",
        body_style
    ))

    story.append(PageBreak())

    # ================= PAGE 4: CAPTURES D'ÉCRAN (PAGE DE CONNEXION & PLANNING) =================
    story.append(Paragraph("PROJET CID — PLATEFORME MÉDICALE WHATSAPP", title_style))
    story.append(Paragraph("Captures d'écran des fonctionnalités développées (Partie 1)", subtitle_style))
    add_divider()
    
    if os.path.exists(IMG_LOGIN):
        story.append(Paragraph("<b>1. Page de Connexion Sécurisée (Split-Screen)</b>", h2_style))
        story.append(Paragraph(
            "L'interface de connexion a été repensée pour offrir un design moderne et professionnel "
            "divisé en deux parties (split-screen). Tous les placeholders génériques ont été supprimés au profit d'un aspect épuré.",
            body_style
        ))
        story.append(Spacer(1, 2))
        story.append(Image(IMG_LOGIN, width=440, height=220))
    else:
        story.append(Paragraph(f"[Erreur] Capture d'écran Connexion non trouvée à : {IMG_LOGIN}", bullet_style))
        
    story.append(Spacer(1, 10))

    if os.path.exists(IMG_PLANNING):
        story.append(Paragraph("<b>2. Onglet Planning des Créneaux & Liste des Patients</b>", h2_style))
        story.append(Paragraph(
            "Cet onglet centralise la gestion clinique : planification dynamique des créneaux médicaux par médecin et spécialité, "
            "visualisation instantanée de l'état des créneaux (libre, réservé par le chatbot, bloqué manuellement) "
            "et liste exhaustive des patients enregistrés avec leur identifiant unique basé sur le numéro WhatsApp.",
            body_style
        ))
        story.append(Spacer(1, 2))
        story.append(Image(IMG_PLANNING, width=440, height=220))
    else:
        story.append(Paragraph(f"[Erreur] Capture d'écran Planning non trouvée à : {IMG_PLANNING}", bullet_style))

    story.append(PageBreak())

    # ================= PAGE 5: CAPTURES D'ÉCRAN (DOSSIER MÉDICAL & AUDIT) =================
    story.append(Paragraph("PROJET CID — PLATEFORME MÉDICALE WHATSAPP", title_style))
    story.append(Paragraph("Captures d'écran des fonctionnalités développées (Partie 2)", subtitle_style))
    add_divider()
    
    if os.path.exists(IMG_MEDICAL):
        story.append(Paragraph("<b>3. Onglet Dossier Médical Centralisé & Saisie d'Analyses</b>", h2_style))
        story.append(Paragraph(
            "Cet onglet permet de sélectionner un patient pour afficher son état civil complet, "
            "son historique de rendez-vous et ses résultats d'analyses. C'est également ici que le laborantin "
            "peut saisir manuellement une analyse (via formulaire dynamique) pour générer automatiquement un PDF officiel chiffré.",
            body_style
        ))
        story.append(Spacer(1, 2))
        story.append(Image(IMG_MEDICAL, width=440, height=220))
    else:
        story.append(Paragraph(f"[Erreur] Capture d'écran Dossier Médical non trouvée à : {IMG_MEDICAL}", bullet_style))
        
    story.append(Spacer(1, 10))

    if os.path.exists(IMG_AUDIT):
        story.append(Paragraph("<b>4. Onglet Gestion des Utilisateurs & Journal d'Audit</b>", h2_style))
        story.append(Paragraph(
            "Permet aux administrateurs de la clinique de gérer les comptes utilisateurs du personnel "
            "(médecins, laborantins, secrétaires) avec attribution des rôles (RBAC). De plus, un journal d'audit sécurisé "
            "enregistre en temps réel toutes les actions critiques réalisées sur la plateforme (connexion, téléchargement, etc.).",
            body_style
        ))
        story.append(Spacer(1, 2))
        story.append(Image(IMG_AUDIT, width=440, height=220))
    else:
        story.append(Paragraph(f"[Erreur] Capture d'écran Journal d'Audit non trouvée à : {IMG_AUDIT}", bullet_style))

    # Page numbering & footer logic
    def add_page_decorations(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#64748b'))
        # Footer
        canvas.drawString(40, 25, "Rapport d'activité & Synthèse Technique - Projet Cid - Confidentiel")
        canvas.drawRightString(doc.pagesize[0]-40, 25, f"Page {doc.page}")
        # Top Header line
        canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
        canvas.setLineWidth(0.5)
        canvas.line(40, doc.pagesize[1]-25, doc.pagesize[0]-40, doc.pagesize[1]-25)
        canvas.drawString(40, doc.pagesize[1]-20, "Cid - Documentation de Synthèse")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_decorations, onLaterPages=add_page_decorations)
    print(f"PDF successfully built at: {OUTPUT_PDF}")

if __name__ == "__main__":
    build_pdf()
