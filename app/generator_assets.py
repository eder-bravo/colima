import os
import zipfile
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

SAMPLES_DIR = os.getenv("SAMPLES_DIR", "/app/data/samples")

def ensure_samples_directory():
    os.makedirs(SAMPLES_DIR, exist_ok=True)

def generate_pdf_cv(filepath: str, name: str, title: str, seniority: str, summary: str, skills: list, experience: list, education: str):
    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Custom styles
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E293B'),
        fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Normal'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#2563EB'),
        fontName='Helvetica-Bold'
    )
    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#0F172A'),
        fontName='Helvetica-Bold',
        spaceBefore=10,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155')
    )
    bold_body = ParagraphStyle(
        'BoldBody',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    elements = []
    
    # Name and Header
    elements.append(Paragraph(name, header_style))
    elements.append(Paragraph(f"{title} | Nivel: {seniority}", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#CBD5E1'), spaceBefore=8, spaceAfter=12))
    
    # Summary
    elements.append(Paragraph("PERFIL PROFESIONAL", section_title))
    elements.append(Paragraph(summary, body_style))
    elements.append(Spacer(1, 8))
    
    # Skills
    elements.append(Paragraph("HABILIDADES TÉCNICAS (ATS KEYWORDS)", section_title))
    skills_text = " • ".join(skills)
    elements.append(Paragraph(f"<b>Core Stack:</b> {skills_text}", body_style))
    elements.append(Spacer(1, 8))
    
    # Experience
    elements.append(Paragraph("EXPERIENCIA LABORAL", section_title))
    for exp in experience:
        elements.append(Paragraph(f"<b>{exp['role']}</b> — {exp['company']} ({exp['period']})", bold_body))
        elements.append(Paragraph(exp['desc'], body_style))
        elements.append(Spacer(1, 4))
    elements.append(Spacer(1, 4))
    
    # Education
    elements.append(Paragraph("EDUCACIÓN & CERTIFICACIONES", section_title))
    elements.append(Paragraph(education, body_style))
    
    doc.build(elements)

def generate_project_brief_pdf(filepath: str):
    doc = SimpleDocTemplate(filepath, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        fontName='Helvetica-Bold'
    )
    sec_style = ParagraphStyle(
        'SecStyle',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#2563EB'),
        fontName='Helvetica-Bold',
        spaceBefore=10,
        spaceAfter=4
    )
    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155')
    )

    elements = [
        Paragraph("PROJECT BRIEF: FINTECH MICRO-LENDING MVP", title_style),
        Paragraph("Objetivo de Negocio: Lanzamiento en 30 días simulados", ParagraphStyle('Sub', parent=body_style, fontName='Helvetica-Bold', textColor=colors.HexColor('#64748B'))),
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#CBD5E1'), spaceBefore=8, spaceAfter=12),
        
        Paragraph("1. RESUMEN DEL PROYECTO", sec_style),
        Paragraph("Desarrollo de una plataforma web y móvil para solicitud y desembolso automático de micro-préstamos para emprendedores en menos de 10 minutos.", body_style),
        Spacer(1, 6),
        
        Paragraph("2. MÓDULOS REQUERIDOS (ALCANCE TÉCNICO)", sec_style),
        Paragraph("<b>Módulo 1: Onboarding & KYC</b><br/>Registro de usuarios con validación facial, OCR de identificación oficial (INE/Pasaporte) y verificación contra buró crediticio.", body_style),
        Spacer(1, 4),
        Paragraph("<b>Módulo 2: Motor de Scoring Crediticio (API)</b><br/>Microservicio en Python/FastAPI con reglas de evaluación de riesgo y aprobación automática de crédito.", body_style),
        Spacer(1, 4),
        Paragraph("<b>Módulo 3: Pasarela de Pagos & Dispersión</b><br/>Integración con SPEI / Stripe / Conekta para dispersión inmediata de fondos y domiciliación de cobro.", body_style),
        Spacer(1, 4),
        Paragraph("<b>Módulo 4: Portal Web de Administración (Backoffice)</b><br/>Dashboard en React para analistas de riesgo, soporte y visualización de cartera vencida.", body_style),
        Spacer(1, 4),
        Paragraph("<b>Módulo 5: Infraestructura Cloud & CI/CD</b><br/>Contenedores Docker, despliegue en Kubernetes/Cloud y pipeline automatizado con pruebas E2E.", body_style),
        Spacer(1, 8),
        
        Paragraph("3. RESTRICCIONES & CRITERIOS DE ÉXITO", sec_style),
        Paragraph("• Cobertura mínima de pruebas unitarias y E2E de 85%.<br/>• Máximo 4 desarrolladores en el equipo base.<br/>• Identificar cuellos de botella en pasarela de pagos y QA temprano.", body_style)
    ]
    
    doc.build(elements)

def generate_all_samples():
    ensure_samples_directory()
    
    cvs = [
        {
            "filename": "1_ana_morales_senior_fullstack.pdf",
            "name": "Ana Morales",
            "title": "Senior Fullstack Engineer",
            "seniority": "Senior (7 años de experiencia)",
            "summary": "Ingeniera de software senior especializada en arquitecturas web distribuidas, microservicios en Python y aplicaciones frontend reactivas de alto rendimiento.",
            "skills": ["Python", "FastAPI", "TypeScript", "React", "Next.js", "PostgreSQL", "Docker", "REST APIs", "Redis"],
            "experience": [
                {"role": "Lead Fullstack Developer", "company": "Fintech Solutions Latam", "period": "2021 - Presente", "desc": "Lideró el desarrollo del core bancario y la pasarela de pagos procesando 50k transacciones diarias."},
                {"role": "Senior Backend Developer", "company": "CloudTech México", "period": "2018 - 2021", "desc": "Diseñó APIs RESTful en Python/FastAPI y optimizó consultas en PostgreSQL reduciendo latencia en 40%."}
            ],
            "education": "Lic. en Ciencias de la Computación (UNAM) | Certificación AWS Solutions Architect"
        },
        {
            "filename": "2_carlos_ruiz_junior_frontend.pdf",
            "name": "Carlos Ruiz",
            "title": "Junior Frontend Developer",
            "seniority": "Junior (1.5 años de experiencia)",
            "summary": "Desarrollador frontend enfocado en interfaces limpias, accesibilidad web y componentes reutilizables con React y TailwindCSS.",
            "skills": ["JavaScript", "HTML5", "CSS3", "React", "TailwindCSS", "Git", "Figma to Code", "Vite"],
            "experience": [
                {"role": "Frontend Developer Trainee", "company": "Agencia Pixel Creativo", "period": "2023 - Presente", "desc": "Desarrollo de landing pages y dashboards interactivos usando React y TailwindCSS."}
            ],
            "education": "Ingeniería en Sistemas Computacionales (TecNM) | Bootcamp Frontend React"
        },
        {
            "filename": "3_lucia_mendez_senior_qa_automation.pdf",
            "name": "Lucía Méndez",
            "title": "Senior QA Automation Engineer",
            "seniority": "Senior (6 años de experiencia)",
            "summary": "Especialista en calidad de software con amplia trayectoria diseñando frameworks de pruebas automatizadas E2E, integración y pruebas de carga para plataformas financieras.",
            "skills": ["QA Automation", "Cypress", "Playwright", "Postman", "Jest", "CI/CD Testing", "TestRail", "K6", "Selenium"],
            "experience": [
                {"role": "Senior QA Lead", "company": "Banco Digital Global", "period": "2020 - Presente", "desc": "Automatizó la suite completa de pruebas de regresión E2E reduciendo el tiempo de testing de 3 días a 35 minutos."},
                {"role": "QA Engineer", "company": "Software QA Labs", "period": "2018 - 2020", "desc": "Creación de planes de prueba y pruebas automatizadas de APIs con Postman y Cypress."}
            ],
            "education": "Ingeniería en Telemática (IPN) | Certificación ISTQB Certified Tester Advanced"
        },
        {
            "filename": "4_roberto_silva_devops_cloud.pdf",
            "name": "Roberto Silva",
            "title": "DevOps & Cloud Engineer",
            "seniority": "Senior (5 años de experiencia)",
            "summary": "Ingeniero DevOps enfocado en automatización de infraestructura como código, observabilidad, contenedores y seguridad en la nube.",
            "skills": ["Docker", "Kubernetes", "Terraform", "GitHub Actions", "AWS", "Oracle Cloud (OCI)", "Prometheus", "Linux", "Nginx"],
            "experience": [
                {"role": "DevOps Specialist", "company": "InnoCloud Systems", "period": "2021 - Presente", "desc": "Implementó pipelines CI/CD automatizados y clusters de Kubernetes de alta disponibilidad con cero downtime."},
                {"role": "SysAdmin & Cloud Ops", "company": "DataCenter Norte", "period": "2019 - 2021", "desc": "Administración de servidores Linux, balanceadores de carga y seguridad perimetral."}
            ],
            "education": "Ingeniería en Computación (UdeG) | Certificación CKA (Certified Kubernetes Administrator)"
        },
        {
            "filename": "5_diego_torres_mid_backend.pdf",
            "name": "Diego Torres",
            "title": "Mid Backend Developer",
            "seniority": "Mid (3 años de experiencia)",
            "summary": "Desarrollador backend orientado a la integración de servicios de terceros, pasarelas de pago y diseño de bases de datos relacionales.",
            "skills": ["Node.js", "Express", "TypeScript", "PostgreSQL", "Stripe API", "SPEI / Webhooks", "Docker", "JWT Auth"],
            "experience": [
                {"role": "Backend Developer", "company": "PayTech Solutions", "period": "2022 - Presente", "desc": "Integró APIs de pagos con Stripe y webhooks bancarios, manejando reconciliación automática de transferencias."},
                {"role": "Junior Backend Dev", "company": "Software Factory MX", "period": "2021 - 2022", "desc": "Desarrollo de endpoints REST y consultas SQL optimizadas para bases de datos relacionales."}
            ],
            "education": "Ingeniería en Software (UANL)"
        }
    ]

    for cv in cvs:
        fp = os.path.join(SAMPLES_DIR, cv["filename"])
        generate_pdf_cv(fp, cv["name"], cv["title"], cv["seniority"], cv["summary"], cv["skills"], cv["experience"], cv["education"])

    brief_path = os.path.join(SAMPLES_DIR, "brief_fintech_microlending_mvp.pdf")
    generate_project_brief_pdf(brief_path)

    # Also build a single ZIP with all files for 1-click download
    zip_path = os.path.join(SAMPLES_DIR, "taller_cvs_pack.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for cv in cvs:
            fp = os.path.join(SAMPLES_DIR, cv["filename"])
            zipf.write(fp, arcname=cv["filename"])
        zipf.write(brief_path, arcname="brief_fintech_microlending_mvp.pdf")
