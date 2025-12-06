"""
Export service - generates PDF reports
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from database import SessionLocal
from sqlalchemy.orm import Session
from models.analysis_job import AnalysisJob
from models.project import Project
from models.issue import Issue
from config import ensure_upload_dir

logger = logging.getLogger(__name__)


class ExportService:
    """Handle report exports"""
    
    def __init__(self):
        self.upload_dir = ensure_upload_dir()
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2563eb'),
            spaceAfter=12,
            spaceBefore=12
        ))
        
        self.styles.add(ParagraphStyle(
            name='IssueTitle',
            parent=self.styles['Normal'],
            fontSize=12,
            textColor=colors.HexColor('#1a1a1a'),
            fontName='Helvetica-Bold',
            spaceAfter=6
        ))
    
    def generate_pdf_sync(self, job_id: str) -> Optional[str]:
        """
        Generate PDF report for analysis job (synchronous version for pre-generation)
        
        Args:
            job_id: Analysis job UUID
            
        Returns:
            Path to generated PDF file
        """
        return self._generate_pdf_internal(job_id)
    
    async def generate_pdf(self, job_id: str) -> Optional[str]:
        """
        Generate PDF report for analysis job (async wrapper)
        
        Args:
            job_id: Analysis job UUID
            
        Returns:
            Path to generated PDF file
        """
        return self._generate_pdf_internal(job_id)
    
    def _generate_pdf_internal(self, job_id: str, db: Session = None) -> Optional[str]:
        """
        Internal PDF generation logic (shared by sync and async versions)
        
        Args:
            job_id: Analysis job UUID
            db: Database session (optional, creates new if not provided)
            
        Returns:
            Path to generated PDF file
        """
        should_close = False
        if db is None:
            from database import SessionLocal
            db = SessionLocal()
            should_close = True
        
        try:
            # Get job and project
            job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return None
            
            project = db.query(Project).filter(Project.id == job.project_id).first()
            if not project:
                logger.error(f"Project {job.project_id} not found")
                return None
            
            # Get issues
            issues = db.query(Issue).filter(Issue.job_id == job_id).all()
            
            # Generate PDF
            pdf_path = self.upload_dir / job.project_id / f"report_{job_id}.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            
            self._create_pdf(pdf_path, job, project, issues)
            
            logger.info(f"Generated PDF report: {pdf_path}")
            return str(pdf_path)
            
        except Exception as e:
            logger.error(f"PDF generation failed: {e}", exc_info=True)
            return None
        
        finally:
            if should_close:
                db.close()
    
    def _create_pdf(self, pdf_path: Path, job: AnalysisJob, project: Project, issues: list):
        """Create PDF document"""
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        story = []
        
        # Title
        story.append(Paragraph("PCB Analysis Report", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.2 * inch))
        
        # Project info
        project_data = [
            ["Project:", project.name],
            ["EDA Tool:", project.eda_tool.upper()],
            ["Board Size:", f"{project.board_size_x} × {project.board_size_y} mm" if project.board_size_x else "N/A"],
            ["Layers:", str(project.layer_count) if project.layer_count else "N/A"],
            ["Analysis Date:", job.completed_at.strftime("%Y-%m-%d %H:%M") if job.completed_at else "N/A"],
        ]
        
        project_table = Table(project_data, colWidths=[2 * inch, 4 * inch])
        project_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        story.append(project_table)
        story.append(Spacer(1, 0.3 * inch))
        
        # Board Summary Section (what does this board do?)
        if job.raw_results and job.raw_results.get('board_summary'):
            board_summary = job.raw_results['board_summary']
            
            story.append(Paragraph("Board Analysis Summary", self.styles['CustomHeading']))
            story.append(Spacer(1, 0.1 * inch))
            
            story.append(Paragraph(f"<b>Purpose:</b> {board_summary.get('purpose', 'Unknown')}", self.styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))
            
            story.append(Paragraph(f"<b>How It Works:</b> {board_summary.get('description', 'N/A')}", self.styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))
            
            if board_summary.get('key_features'):
                story.append(Paragraph("<b>Key Features:</b>", self.styles['Normal']))
                for feature in board_summary.get('key_features', []):
                    story.append(Paragraph(f"• {feature}", self.styles['Normal']))
                story.append(Spacer(1, 0.1 * inch))
            
            if board_summary.get('main_components'):
                story.append(Paragraph("<b>Main Components:</b>", self.styles['Normal']))
                for comp in board_summary.get('main_components', []):
                    story.append(Paragraph(f"• {comp}", self.styles['Normal']))
                story.append(Spacer(1, 0.1 * inch))
            
            if board_summary.get('design_notes'):
                story.append(Paragraph(f"<b>Design Notes:</b> {board_summary.get('design_notes', '')}", self.styles['Normal']))
            
            story.append(Spacer(1, 0.3 * inch))
        
        # Summary
        story.append(Paragraph("Executive Summary", self.styles['CustomHeading']))
        
        # Handle None risk_level (if analysis failed before completion)
        risk_level = job.risk_level or "unknown"
        risk_color = {
            'low': colors.green,
            'moderate': colors.orange,
            'high': colors.red,
            'unknown': colors.grey
        }.get(risk_level, colors.grey)
        
        risk_text = f"<font color='{risk_color.hexval()}'>Risk Level: {risk_level.upper()}</font>"
        story.append(Paragraph(risk_text, self.styles['Normal']))
        story.append(Spacer(1, 0.1 * inch))
        
        summary_data = [
            ["🔴 Critical Issues:", job.critical_count or "0"],
            ["⚠️ Warnings:", job.warning_count or "0"],
            ["ℹ️ Info:", job.info_count or "0"],
            ["Total Issues:", str(len(issues))],
        ]
        
        summary_table = Table(summary_data, colWidths=[3 * inch, 1.5 * inch])
        summary_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEBELOW', (0, -1), (-1, -1), 1, colors.grey),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 0.3 * inch))
        
        # Issues by category
        categories = {}
        for issue in issues:
            if issue.category not in categories:
                categories[issue.category] = []
            categories[issue.category].append(issue)
        
        for category, cat_issues in categories.items():
            story.append(PageBreak())
            
            # Category heading
            category_title = category.replace('_', ' ').title()
            story.append(Paragraph(f"Category: {category_title}", self.styles['CustomHeading']))
            story.append(Spacer(1, 0.1 * inch))
            
            # Issues in category
            for issue in cat_issues:
                # Severity badge
                severity_color = {
                    'critical': colors.red,
                    'warning': colors.orange,
                    'info': colors.blue
                }.get(issue.severity, colors.grey)
                
                severity_text = f"<font color='{severity_color.hexval()}'>[{issue.severity.upper()}]</font>"
                
                # Issue code and title
                title_text = f"{severity_text} <b>{issue.issue_code}:</b> {issue.title}"
                story.append(Paragraph(title_text, self.styles['IssueTitle']))
                
                # Description
                story.append(Paragraph(f"<b>Description:</b> {issue.description}", self.styles['Normal']))
                story.append(Spacer(1, 0.05 * inch))
                
                # Suggested fix
                fix_text = issue.suggested_fix.replace('\n', '<br/>')
                story.append(Paragraph(f"<b>Suggested Fix:</b><br/>{fix_text}", self.styles['Normal']))
                
                # Affected components/nets
                if issue.affected_components:
                    comps = ', '.join(issue.affected_components[:10])
                    if len(issue.affected_components) > 10:
                        comps += f" ... and {len(issue.affected_components) - 10} more"
                    story.append(Paragraph(f"<b>Affected Components:</b> {comps}", self.styles['Normal']))
                
                if issue.affected_nets:
                    nets = ', '.join(issue.affected_nets[:10])
                    if len(issue.affected_nets) > 10:
                        nets += f" ... and {len(issue.affected_nets) - 10} more"
                    story.append(Paragraph(f"<b>Affected Nets:</b> {nets}", self.styles['Normal']))
                
                story.append(Spacer(1, 0.2 * inch))
        
        # Top 5 Improvement Suggestions Section
        if job.raw_results and job.raw_results.get('ai_suggestions'):
            story.append(Spacer(1, 0.4 * inch))
            story.append(Paragraph("💡 Top 5 Improvement Suggestions", self.styles['CustomHeading']))
            story.append(Paragraph("Beyond fixing the issues above, consider these design improvements:", self.styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))
            
            suggestions = job.raw_results.get('ai_suggestions', [])[:5]  # Top 5
            for idx, suggestion in enumerate(suggestions, 1):
                priority_color = {
                    'high': colors.HexColor('#FF6B6B'),
                    'medium': colors.HexColor('#FFA500'),
                    'low': colors.HexColor('#4ECDC4')
                }.get(suggestion.get('priority', 'medium').lower(), colors.grey)
                
                priority_badge = f"<font color='{priority_color.hexval()}'>[{suggestion.get('priority', 'MEDIUM').upper()}]</font>"
                
                story.append(Paragraph(
                    f"{priority_badge} <b>{idx}. {suggestion.get('title', 'Untitled suggestion')}</b>",
                    self.styles['IssueTitle']
                ))
                story.append(Spacer(1, 0.05 * inch))
                
                story.append(Paragraph(
                    f"<b>Description:</b> {suggestion.get('description', 'No description')}",
                    self.styles['Normal']
                ))
                story.append(Spacer(1, 0.05 * inch))
                
                story.append(Paragraph(
                    f"<b>Benefit:</b> {suggestion.get('benefit', 'Improved design quality')}",
                    self.styles['Normal']
                ))
                story.append(Spacer(1, 0.2 * inch))
        
        # Footer
        story.append(PageBreak())
        story.append(Spacer(1, 2 * inch))
        story.append(Paragraph(
            "Generated by PCB Analyzer - Building Automation Edition",
            self.styles['Normal']
        ))
        story.append(Paragraph(
            f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            self.styles['Normal']
        ))
        
        # Build PDF
        doc.build(story)
    
    def generate_pdf_for_supabase(self, analysis_id: str, results: dict, organization_id: str) -> Optional[str]:
        """
        Generate PDF report from pre-computed results (for Supabase-based analyses)
        
        Args:
            analysis_id: Analysis UUID
            results: Dictionary with board_info, board_summary, issues, summary, risk_level
            organization_id: Organization UUID for storage path
            
        Returns:
            Path to generated PDF file (for upload to Supabase Storage)
        """
        try:
            # Create PDF path
            pdf_path = self.upload_dir / analysis_id / f"report_{analysis_id}.pdf"
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build PDF document
            doc = SimpleDocTemplate(
                str(pdf_path),
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            story = []
            
            # Title
            story.append(Paragraph("PCB Analysis Report", self.styles['CustomTitle']))
            story.append(Spacer(1, 0.2 * inch))
            
            # Board info
            board_info = results.get('board_info', {})
            project_data = [
                ["Board Size:", f"{board_info.get('size_x', 0)} × {board_info.get('size_y', 0)} mm"],
                ["Layers:", str(board_info.get('layer_count', 'N/A'))],
                ["Components:", str(board_info.get('components_count', 0))],
                ["Nets:", str(board_info.get('nets_count', 0))],
                ["EDA Tool:", board_info.get('eda_tool', 'Unknown').upper()],
                ["Analysis Date:", datetime.now().strftime("%Y-%m-%d %H:%M")],
            ]
            
            project_table = Table(project_data, colWidths=[2 * inch, 4 * inch])
            project_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            story.append(project_table)
            story.append(Spacer(1, 0.3 * inch))
            
            # Board Summary
            board_summary = results.get('board_summary', {})
            if board_summary:
                story.append(Paragraph("Board Analysis Summary", self.styles['CustomHeading']))
                story.append(Spacer(1, 0.1 * inch))
                
                story.append(Paragraph(f"<b>Purpose:</b> {board_summary.get('purpose', 'Unknown')}", self.styles['Normal']))
                story.append(Spacer(1, 0.1 * inch))
                
                story.append(Paragraph(f"<b>Description:</b> {board_summary.get('description', 'N/A')}", self.styles['Normal']))
                story.append(Spacer(1, 0.1 * inch))
                
                if board_summary.get('key_features'):
                    story.append(Paragraph("<b>Key Features:</b>", self.styles['Normal']))
                    for feature in board_summary.get('key_features', [])[:5]:
                        story.append(Paragraph(f"• {feature}", self.styles['Normal']))
                    story.append(Spacer(1, 0.1 * inch))
                
                story.append(Spacer(1, 0.3 * inch))
            
            # Risk Summary
            story.append(Paragraph("Executive Summary", self.styles['CustomHeading']))
            
            risk_level = results.get('risk_level', 'unknown')
            risk_color = {
                'low': colors.green,
                'moderate': colors.orange,
                'high': colors.red,
                'unknown': colors.grey
            }.get(risk_level, colors.grey)
            
            risk_text = f"<font color='{risk_color.hexval()}'>Risk Level: {risk_level.upper()}</font>"
            story.append(Paragraph(risk_text, self.styles['Normal']))
            story.append(Spacer(1, 0.1 * inch))
            
            summary = results.get('summary', {})
            summary_data = [
                ["🔴 Critical Issues:", str(summary.get('critical', 0))],
                ["⚠️ Warnings:", str(summary.get('warning', 0))],
                ["ℹ️ Info:", str(summary.get('info', 0))],
                ["Total Issues:", str(len(results.get('issues', [])))],
            ]
            
            summary_table = Table(summary_data, colWidths=[3 * inch, 1.5 * inch])
            summary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ]))
            
            story.append(summary_table)
            story.append(Spacer(1, 0.3 * inch))
            
            # Issues
            issues = results.get('issues', [])
            if issues:
                story.append(Paragraph("Issues Found", self.styles['CustomHeading']))
                story.append(Spacer(1, 0.1 * inch))
                
                # Group by severity
                for severity in ['critical', 'warning', 'info']:
                    severity_issues = [i for i in issues if i.get('severity') == severity]
                    if severity_issues:
                        severity_color = {'critical': colors.red, 'warning': colors.orange, 'info': colors.blue}.get(severity, colors.grey)
                        story.append(Paragraph(f"<font color='{severity_color.hexval()}'><b>{severity.upper()} ({len(severity_issues)})</b></font>", self.styles['Normal']))
                        story.append(Spacer(1, 0.05 * inch))
                        
                        for issue in severity_issues[:10]:  # Limit to 10 per category
                            story.append(Paragraph(f"• <b>{issue.get('title', 'Unknown Issue')}</b>", self.styles['Normal']))
                            if issue.get('description'):
                                story.append(Paragraph(f"  {issue.get('description')[:200]}", self.styles['Normal']))
                            story.append(Spacer(1, 0.05 * inch))
                        
                        story.append(Spacer(1, 0.1 * inch))
            
            # Footer
            story.append(Spacer(1, 0.5 * inch))
            story.append(Paragraph(
                "Generated by BoardMint PCB Analyzer",
                self.styles['Normal']
            ))
            story.append(Paragraph(
                f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                self.styles['Normal']
            ))
            
            # Build PDF
            doc.build(story)
            
            logger.info(f"✅ PDF generated for Supabase analysis: {pdf_path}")
            
            # Optionally upload to Supabase Storage
            try:
                from supabase_client import get_supabase
                supabase = get_supabase()
                
                storage_path = f"org_{organization_id}/reports/{analysis_id}/report.pdf"
                
                with open(pdf_path, 'rb') as f:
                    pdf_content = f.read()
                
                supabase.storage.from_("analysis-reports").upload(
                    storage_path,
                    pdf_content,
                    {"content-type": "application/pdf"}
                )
                
                logger.info(f"✅ PDF uploaded to Supabase: {storage_path}")
                return storage_path
                
            except Exception as upload_error:
                logger.warning(f"⚠️ PDF upload to Supabase failed: {upload_error}")
                # Return local path as fallback
                return str(pdf_path)
            
        except Exception as e:
            logger.error(f"❌ PDF generation failed: {e}", exc_info=True)
            return None
