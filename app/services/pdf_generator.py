import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def generate_medical_pdf(
    patient_name: str,
    patient_dob: str = "",
    patient_whatsapp: str = "",
    patient_id: int = 0,
    analysis_type: str = "Bilan Biologique",
    analysis_date: str = "",
    template_type: str = "custom",
    results_data: dict | None = None,
) -> bytes:
    """
    Génère un PDF officiel de compte-rendu d'analyse médicale.
    """
    if results_data is None:
        results_data = {}

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    story = []

    # Styles
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ClinicTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#0f3a60'),
        alignment=0,
        spaceAfter=2
    )
    specialties_style = ParagraphStyle(
        'ClinicSpecialties',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        textColor=colors.HexColor('#0284c7'),
        spaceAfter=3
    )
    subtitle_style = ParagraphStyle(
        'ClinicSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=10
    )
    section_title = ParagraphStyle(
        'SecTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        textColor=colors.HexColor('#0f3a60'),
        spaceBefore=14,
        spaceAfter=8
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.HexColor('#0f172a')
    )
    body_normal = ParagraphStyle(
        'BodyNorm',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#334155')
    )
    cell_header = ParagraphStyle(
        'CellHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.white
    )

    # 1. En-tête de la Clinique
    story.append(Paragraph("CLINIQUE MÉDICALE & LABORATOIRE", title_style))
    story.append(Paragraph("Cardiologie · Médecine générale · Analyses biomédicales", specialties_style))
    story.append(Paragraph("Plateforme Numérique de Gestion des Résultats et Analyses Médicales", subtitle_style))

    # Ligne de séparation clinique élégante
    divider = Table([['']], colWidths=[532], rowHeights=[2.5])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0284c7')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 14))

    # 2. Deux blocs : Dossier Patient & Information sur l'Analyse
    gen_date = datetime.now().strftime('%d/%m/%Y à %H:%M')
    info_data = [
        [
            Paragraph("<b>DOSSIER PATIENT</b>", body_bold),
            Paragraph("<b>INFORMATIONS SUR L'ANALYSE</b>", body_bold)
        ],
        [
            Paragraph(f"<b>Nom & Prénom :</b> {patient_name.upper()}", body_normal),
            Paragraph(f"<b>Type d'Analyse :</b> {analysis_type}", body_normal)
        ],
        [
            Paragraph(f"<b>Contact WhatsApp :</b> {patient_whatsapp}", body_normal),
            Paragraph(f"<b>Date d'Analyse :</b> {analysis_date or datetime.now().strftime('%d/%m/%Y')}", body_normal)
        ],
        [
            Paragraph("<b>Prise en charge :</b> Ambulatoire / Externe", body_normal),
            Paragraph(f"<b>Édité le :</b> {gen_date}", body_normal)
        ],
        [
            Paragraph("", body_normal),
            Paragraph("<b>Statut :</b> <font color='#047857'><b>Validé électroniquement</b></font>", body_normal)
        ]
    ]

    info_table = Table(info_data, colWidths=[266, 266])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#f1f5f9')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#f1f5f9')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#0284c7')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 10))

    # 3. Tableau des Résultats
    story.append(Paragraph("RÉSULTATS BIOMÉDICAUX", section_title))

    table_headers = [
        Paragraph("Paramètre / Examen", cell_header),
        Paragraph("Résultat", cell_header),
        Paragraph("Valeurs de Référence", cell_header),
        Paragraph("Unité", cell_header)
    ]
    rows = [table_headers]

    if template_type == "blood":
        blood_params = [
            ("Glycémie à jeun", "glycemie", "0.70 - 1.10", "g/L"),
            ("Cholestérol Total", "cholesterol", "< 2.00", "g/L"),
            ("Triglycérides", "triglycerides", "0.35 - 1.50", "g/L"),
            ("Urée Sérique", "uree", "0.15 - 0.50", "g/L"),
            ("Créatinine", "creatinine", "5.0 - 12.0", "mg/L"),
        ]
        for label, key, ref, unit in blood_params:
            val = results_data.get(key, "N/A")
            rows.append([
                Paragraph(label, body_bold),
                Paragraph(f"<b>{val}</b>", body_normal),
                Paragraph(ref, body_normal),
                Paragraph(unit, body_normal),
            ])
    elif template_type == "urine":
        urine_params = [
            ("Aspect de l'urine", "aspect", "Clair / Jaune ambré", "-"),
            ("pH urinaire", "ph", "4.5 - 8.0", "-"),
            ("Protéinurie (Albument)", "proteines", "Négatif", "-"),
            ("Glucosurie", "glucose", "Négatif", "-"),
            ("Leucocytes urinaires", "leucocytes", "< 10", "/µL"),
        ]
        for label, key, ref, unit in urine_params:
            val = results_data.get(key, "N/A")
            rows.append([
                Paragraph(label, body_bold),
                Paragraph(f"<b>{val}</b>", body_normal),
                Paragraph(ref, body_normal),
                Paragraph(unit, body_normal),
            ])
    elif template_type == "lipid":
        lipid_params = [
            ("Cholestérol Total", "cholesterol_total", "< 2.00", "g/L"),
            ("Cholestérol HDL (Protecteur)", "cholesterol_hdl", "> 0.40", "g/L"),
            ("Cholestérol LDL (Athérogène)", "cholesterol_ldl", "< 1.30", "g/L"),
            ("Triglycérides", "triglycerides_lipid", "< 1.50", "g/L"),
        ]
        for label, key, ref, unit in lipid_params:
            val = results_data.get(key, "N/A")
            rows.append([
                Paragraph(label, body_bold),
                Paragraph(f"<b>{val}</b>", body_normal),
                Paragraph(ref, body_normal),
                Paragraph(unit, body_normal),
            ])
    else:  # Custom / Libre
        notes_val = results_data.get("notes", "").replace("\n", "<br/>")
        rows = None

    if rows:
        results_table = Table(rows, colWidths=[180, 112, 160, 80])
        results_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f3a60')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(results_table)
    else:
        # Notes block for custom results
        notes_data = [
            [Paragraph("<b>Détail des Examens & Observations :</b>", body_bold)],
            [Paragraph(notes_val if notes_val else "Examens biologiques conformes aux spécifications requises.", body_normal)]
        ]
        notes_table = Table(notes_data, colWidths=[532])
        notes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(notes_table)

    story.append(Spacer(1, 14))

    # 4. Section Conclusion Biologique
    story.append(Paragraph("CONCLUSION BIOLOGIQUE", section_title))
    conclusion_text = (
        "Examens et analyses réalisés sous la responsabilité du biologiste médical de la clinique. "
        "Les résultats ci-dessus sont validés conformément aux protocoles d'analyses cliniques et de contrôle qualité en vigueur."
    )
    if template_type not in ["blood", "urine", "lipid"] and results_data.get("notes"):
        conclusion_text = "Rapport biologique certifié conforme aux constats cliniques et aux référentiels du laboratoire."

    conclusion_data = [
        [Paragraph(f"<i>{conclusion_text}</i>", body_normal)]
    ]
    conclusion_table = Table(conclusion_data, colWidths=[532])
    conclusion_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0fdf4')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#86efac')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(conclusion_table)

    story.append(Spacer(1, 20))

    # 5. Bloc Signature (Biologiste responsable)
    sig_data = [
        ["", Paragraph("<b>Le Biologiste Responsable</b>", body_bold)],
        ["", Paragraph("Validation & Certification Électronique", body_normal)],
        ["", Paragraph("<b>Dr. M. KEREKOU</b> / Biologie Médicale", body_normal)],
        ["", Paragraph("<font color='#0284c7'>[Cachet & Signature Électronique Certifiés]</font>", body_normal)]
    ]
    sig_table = Table(sig_data, colWidths=[312, 220])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sig_table)

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_appointment_pdf(
    patient_name: str,
    patient_id: int = 0,
    patient_whatsapp: str = "",
    appointment_id: int = 0,
    doctor_name: str = "",
    specialty: str = "",
    appointment_date: str = "",
    appointment_time: str = "",
) -> bytes:
    """
    Génère un PDF officiel de confirmation de rendez-vous médical.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    story = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ClinicTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#0f3a60'),
        alignment=0,
        spaceAfter=2
    )
    specialties_style = ParagraphStyle(
        'ClinicSpecialties',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        textColor=colors.HexColor('#0284c7'),
        spaceAfter=3
    )
    subtitle_style = ParagraphStyle(
        'ClinicSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=10
    )
    section_title = ParagraphStyle(
        'SecTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#0f3a60'),
        spaceBefore=14,
        spaceAfter=10
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        textColor=colors.HexColor('#0f172a')
    )
    body_normal = ParagraphStyle(
        'BodyNorm',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        textColor=colors.HexColor('#334155')
    )

    # 1. En-tête
    story.append(Paragraph("CLINIQUE MÉDICALE & LABORATOIRE", title_style))
    story.append(Paragraph("Cardiologie · Médecine générale · Analyses biomédicales", specialties_style))
    story.append(Paragraph("Confirmation Officielle de Rendez-vous Médical", subtitle_style))

    divider = Table([['']], colWidths=[532], rowHeights=[2.5])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0284c7')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 15))

    # 2. Tableau Récapitulatif
    story.append(Paragraph("RÉCAPITULATIF DU RENDEZ-VOUS", section_title))

    info_data = [
        [Paragraph("<b>Numéro de Référence :</b>", body_bold), Paragraph(f"<b>#{appointment_id}</b>", body_bold)],
        [Paragraph("<b>Nom du Patient :</b>", body_bold), Paragraph(patient_name.upper(), body_normal)],
        [Paragraph("<b>Contact WhatsApp :</b>", body_bold), Paragraph(patient_whatsapp, body_normal)],
        [Paragraph("<b>Médecin traitant :</b>", body_bold), Paragraph(doctor_name, body_normal)],
        [Paragraph("<b>Spécialité :</b>", body_bold), Paragraph(specialty, body_normal)],
        [Paragraph("<b>Date de consultation :</b>", body_bold), Paragraph(appointment_date, body_normal)],
        [Paragraph("<b>Heure du rendez-vous :</b>", body_bold), Paragraph(appointment_time, body_normal)],
        [Paragraph("<b>Statut :</b>", body_bold), Paragraph("<font color='#047857'><b>Validé</b></font>", body_bold)],
    ]

    info_table = Table(info_data, colWidths=[172, 360])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    story.append(info_table)
    story.append(Spacer(1, 18))

    # 3. Note aux patients
    note_data = [
        [
            Paragraph("<b>Note aux patients :</b>", body_bold)
        ],
        [
            Paragraph(
                "Ce rendez-vous a été validé par le secrétariat de la clinique. "
                "Veuillez conserver le numéro de référence pour toute modification ou annulation.",
                body_normal
            )
        ]
    ]
    note_table = Table(note_data, colWidths=[532])
    note_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eff6ff')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#bfdbfe')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(note_table)

    # Pas de pied de page (supprimé entièrement)
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
