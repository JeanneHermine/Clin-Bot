import io
from datetime import date, datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def generate_medical_pdf(
    patient_name: str,
    patient_dob: str,
    patient_whatsapp: str,
    patient_id: int,
    analysis_type: str,
    analysis_date: str,
    template_type: str,
    results_data: dict,
) -> bytes:

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

    styles = getSampleStyleSheet()
    

    title_style = ParagraphStyle(
        'ClinicTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=0,
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'ClinicSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )
    section_title = ParagraphStyle(
        'SecTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=colors.HexColor('#0d9488'),
        spaceBefore=12,
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


    story.append(Paragraph("Cid - CLINIQUE MÉDICALE & LABORATOIRE", title_style))
    story.append(Paragraph("Plateforme Numérique de Gestion des Résultats et Analyses Médicales", subtitle_style))
    
    divider = Table([['']], colWidths=[530], rowHeights=[2])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0d9488')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 15))

    info_data = [
        [
            Paragraph("<b>DOSSIER PATIENT</b>", body_bold),
            Paragraph("<b>INFORMATION ANALYSE</b>", body_bold)
        ],
        [
            Paragraph(f"Patient ID : #{patient_id}", body_normal),
            Paragraph(f"Type d'Analyse : {analysis_type}", body_normal)
        ],
        [
            Paragraph(f"Nom : {patient_name.upper()}", body_normal),
            Paragraph(f"Date d'Analyse : {analysis_date}", body_normal)
        ],
        [
            Paragraph(f"Né(e) le : {patient_dob}", body_normal),
            Paragraph(f"Date de Génération : {datetime.now().strftime('%d/%m/%Y %H:%M')}", body_normal)
        ],
        [
            Paragraph(f"WhatsApp : {patient_whatsapp}", body_normal),
            Paragraph("Statut : Validé électroniquement", body_bold)
        ]
    ]
    info_table = Table(info_data, colWidths=[265, 265])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#f1f5f9')),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#cbd5e1')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("RÉSULTATS DE LABORATOIRE", section_title))
    
    table_headers = [
        Paragraph("Paramètre", cell_header),
        Paragraph("Résultat Saisi", cell_header),
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
            ("Aspect de l'urine", "aspect", "Clair / Jaune pâle", "-"),
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
            ("Cholestérol HDL (Bon)", "cholesterol_hdl", "> 0.40", "g/L"),
            ("Cholestérol LDL (Mauvais)", "cholesterol_ldl", "< 1.30", "g/L"),
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
        # Display the custom key-values, or a single comment block
        notes_val = results_data.get("notes", "").replace("\n", "<br/>")
        rows = None  # We won't display a parameters table, but a rich note block instead

    if rows:
        results_table = Table(rows, colWidths=[180, 110, 160, 80])
        results_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(results_table)
    else:
        # Notes block for custom results
        notes_data = [
            [Paragraph("<b>Rapport d'Analyse / Conclusions :</b>", body_bold)],
            [Paragraph(notes_val if notes_val else "Aucune observation particulière renseignée.", body_normal)]
        ]
        notes_table = Table(notes_data, colWidths=[530])
        notes_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ]))
        story.append(notes_table)

    story.append(Spacer(1, 30))

    # 4. Signature block
    sig_data = [
        ["", "<b>Laborantin Responsable</b>"],
        ["", "Signature & Cachet Électronique"],
        ["", ""],
        ["", "Document chiffré au repos (Fernet AES-256)"]
    ]
    sig_table = Table(sig_data, colWidths=[330, 200])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(sig_table)
    
    # Page Footer note
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Oblique', 8)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(40, 20, "Attention : Ce document est strictement confidentiel. Transmis de manière sécurisée.")
        canvas.drawRightString(doc.pagesize[0]-40, 20, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_appointment_pdf(
    patient_name: str,
    patient_id: int,
    patient_whatsapp: str,
    appointment_id: int,
    doctor_name: str,
    specialty: str,
    appointment_date: str,
    appointment_time: str,
) -> bytes:
    """
    Génère un PDF officiel de confirmation de demande de rendez-vous.
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
        fontSize=20,
        textColor=colors.HexColor('#1e3a8a'),
        alignment=0,
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'ClinicSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )
    section_title = ParagraphStyle(
        'SecTitle',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        textColor=colors.HexColor('#0d9488'),
        spaceBefore=15,
        spaceAfter=10
    )
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.HexColor('#0f172a')
    )
    body_normal = ParagraphStyle(
        'BodyNorm',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#334155')
    )

    story.append(Paragraph("Cid - CLINIQUE MÉDICALE & LABORATOIRE", title_style))
    story.append(Paragraph("Confirmation Officielle de Demande de Rendez-vous", subtitle_style))
    
    divider = Table([['']], colWidths=[530], rowHeights=[2])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#0d9488')),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 15))

    story.append(Paragraph("RÉCAPITULATIF DU RENDEZ-VOUS", section_title))
    
    info_data = [
        [Paragraph("<b>Référence RDV :</b>", body_bold), Paragraph(f"#{appointment_id}", body_normal)],
        [Paragraph("<b>Patient ID :</b>", body_bold), Paragraph(f"#{patient_id}", body_normal)],
        [Paragraph("<b>Nom du Patient :</b>", body_bold), Paragraph(patient_name.upper(), body_normal)],
        [Paragraph("<b>Numéro WhatsApp :</b>", body_bold), Paragraph(patient_whatsapp, body_normal)],
        [Paragraph("<b>Médecin :</b>", body_bold), Paragraph(doctor_name, body_normal)],
        [Paragraph("<b>Spécialité :</b>", body_bold), Paragraph(specialty, body_normal)],
        [Paragraph("<b>Date :</b>", body_bold), Paragraph(appointment_date, body_normal)],
        [Paragraph("<b>Heure :</b>", body_bold), Paragraph(appointment_time, body_normal)],
        [Paragraph("<b>Statut de la demande :</b>", body_bold), Paragraph("En attente de validation par la clinique", body_bold)],
    ]
    
    info_table = Table(info_data, colWidths=[150, 380])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("<b>Note aux patients :</b>", body_bold))
    story.append(Paragraph(
        "Ce document atteste de votre demande de rendez-vous via notre assistant automatique. "
        "Le secrétariat de la clinique validera cette demande sous peu. "
        "En cas de modification ou d'annulation, veuillez vous munir du numéro de référence du rendez-vous.",
        body_normal
    ))
    
    def add_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica-Oblique', 8)
        canvas.setFillColor(colors.HexColor('#64748b'))
        canvas.drawString(40, 20, "Cid - Service de planification automatisé.")
        canvas.drawRightString(doc.pagesize[0]-40, 20, f"Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        canvas.restoreState()

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
