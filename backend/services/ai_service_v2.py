"""
AI Analysis Service V2 - RAG-Powered PCB Analysis
Professional-grade AI analysis using retrieval-augmented generation

Features:
- RAG integration with PCB knowledge bases
- Vision capabilities for layout analysis
- Expert prompt engineering
- Multi-stage analysis pipeline
- Evidence-based issue detection
"""

import os
import json
import base64
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

from openai import OpenAI
from config import get_settings
from rules.base_rule import Issue, IssueSeverity

from .knowledge_base.rag_retriever import RAGRetriever, RetrievalContext

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Complete AI analysis result"""
    issues: List[Issue]
    suggestions: List[Dict[str, str]]
    expert_insights: List[Dict[str, str]]
    standards_applied: List[str]
    confidence_score: float


class AIAnalysisServiceV2:
    """
    Professional AI-Powered PCB Analysis Service
    
    Uses RAG to augment GPT-4 with domain expertise from:
    - IPC/IEC/UL standards
    - TI/NXP application notes
    - Industry design guides
    
    Implements multi-stage analysis:
    1. Context extraction from PCB data
    2. RAG retrieval of relevant knowledge
    3. Expert analysis with evidence
    4. Vision analysis of layout images (optional)
    """
    
    def __init__(self):
        """Initialize AI service with RAG"""
        settings = get_settings()
        self.enabled = settings.enable_ai_analysis and settings.openai_api_key
        
        if self.enabled:
            self.client = OpenAI(api_key=settings.openai_api_key)
            self.model = settings.openai_model
            self.vision_model = "gpt-4o"  # For image analysis
            
            # Initialize RAG retriever
            project_root = Path(__file__).parent.parent.parent
            self.rag = RAGRetriever(project_root=str(project_root))
            
            logger.info(f"AI Service V2 initialized: model={self.model}, RAG enabled")
        else:
            logger.info("AI Analysis disabled (no API key or disabled in config)")
    
    def analyze_pcb(
        self,
        project_path: Path,
        parsed_data: Dict[str, Any],
        rule_engine_issues: List[Issue],
        fab_profile: str,
        layout_images: Optional[List[str]] = None
    ) -> AnalysisResult:
        """
        Comprehensive AI analysis of PCB design
        
        Args:
            project_path: Path to project files
            parsed_data: Parsed PCB data
            rule_engine_issues: Issues from rule engines
            fab_profile: Fabrication profile
            layout_images: Optional layout screenshots for vision analysis
        
        Returns:
            AnalysisResult with issues, suggestions, and insights
        """
        if not self.enabled:
            return AnalysisResult(
                issues=[],
                suggestions=[],
                expert_insights=[],
                standards_applied=[],
                confidence_score=0.0
            )
        
        try:
            logger.info("Starting AI analysis pipeline...")
            
            # Stage 1: Detect design topics
            topics = self._detect_design_topics(parsed_data)
            logger.info(f"Detected topics: {topics}")
            
            # Stage 2: Retrieve relevant knowledge
            rag_context = self.rag.retrieve_for_analysis(
                pcb_context=parsed_data,
                detected_topics=topics,
                max_chunks=8
            )
            logger.info(f"Retrieved {rag_context.total_chunks} knowledge chunks")
            
            # Stage 3: Build expert context
            expert_context = self._build_expert_context(
                parsed_data, rule_engine_issues, fab_profile, rag_context
            )
            
            # Stage 4: AI expert analysis
            ai_result = self._run_expert_analysis(expert_context)
            
            # Stage 5: Optional vision analysis
            if layout_images:
                vision_issues = self._run_vision_analysis(layout_images, parsed_data)
                ai_result.issues.extend(vision_issues)
            
            # Stage 6: Validate and filter results
            validated_result = self._validate_results(ai_result, rule_engine_issues)
            
            logger.info(f"AI analysis complete: {len(validated_result.issues)} issues, "
                       f"{len(validated_result.suggestions)} suggestions")
            
            return validated_result
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}", exc_info=True)
            return AnalysisResult(
                issues=[],
                suggestions=[],
                expert_insights=[],
                standards_applied=[],
                confidence_score=0.0
            )
    
    def _detect_design_topics(self, parsed_data: Dict) -> List[str]:
        """Detect relevant topics from PCB data"""
        topics = []
        
        nets = parsed_data.get('nets', [])
        components = parsed_data.get('components', [])
        
        net_names = ' '.join([n.get('name', '') for n in nets]).lower()
        comp_values = ' '.join([c.get('value', '') for c in components]).lower()
        combined = net_names + ' ' + comp_values
        
        # Topic detection rules
        topic_rules = {
            'power_supply': ['vin', 'vout', '3v3', '5v', '12v', 'regulator', 'ldo', 'buck', 'boost'],
            'safety': ['mains', '230v', '120v', 'ac_', 'isolation', 'optocoupler'],
            'bus_interface': ['i2c', 'sda', 'scl', 'spi', 'mosi', 'miso', 'rs485', 'can_', 'uart'],
            'high_speed': ['usb', 'pcie', 'hdmi', 'eth', 'rgmii', 'lvds'],
            'wireless': ['wifi', 'ble', 'zigbee', 'lora', 'antenna', 'rf_'],
            'thermal': ['heatsink', 'thermal', 'fan', 'temp'],
            'emc_emi': ['filter', 'ferrite', 'shield', 'esd', 'tvs'],
        }
        
        for topic, keywords in topic_rules.items():
            if any(kw in combined for kw in keywords):
                topics.append(topic)
        
        # Default topics if none detected
        if not topics:
            topics = ['layout', 'components']
        
        return topics
    
    def _build_expert_context(
        self,
        parsed_data: Dict,
        rule_engine_issues: List[Issue],
        fab_profile: str,
        rag_context: RetrievalContext
    ) -> str:
        """Build comprehensive expert context for AI analysis"""
        
        board_info = parsed_data.get('board_info', {})
        nets = parsed_data.get('nets', [])
        components = parsed_data.get('components', [])
        
        # Count issues by severity
        critical_count = sum(1 for i in rule_engine_issues if i.severity == IssueSeverity.CRITICAL)
        error_count = sum(1 for i in rule_engine_issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in rule_engine_issues if i.severity == IssueSeverity.WARNING)
        
        context = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          PCB DESIGN ANALYSIS CONTEXT                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 BOARD SPECIFICATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Dimensions: {board_info.get('size_x_mm', 'N/A')} × {board_info.get('size_y_mm', 'N/A')} mm
• Layer Count: {board_info.get('layer_count', 'N/A')}
• Fabrication Profile: {fab_profile}
• Total Nets: {len(nets)}
• Total Components: {len(components)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ CRITICAL NETS IDENTIFIED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{self._format_critical_nets(nets)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 KEY COMPONENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{self._format_key_components(components)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 AUTOMATED RULE ENGINE RESULTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Critical Issues: {critical_count}
• Errors: {error_count}
• Warnings: {warning_count}

Top Issues Found:
{self._format_rule_engine_issues(rule_engine_issues[:15])}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 RELEVANT KNOWLEDGE BASE CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sources: {', '.join(rag_context.sources[:5])}
Standards Referenced: {', '.join(rag_context.standards_referenced[:5])}
Topics: {', '.join(rag_context.topics_covered[:5])}

{rag_context.context_text[:8000]}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return context
    
    def _format_critical_nets(self, nets: List[Dict]) -> str:
        """Format critical nets for context"""
        critical_patterns = {
            'power': ['vcc', 'vdd', '3v3', '5v', '12v', '24v', 'vin', 'vout', 'vbat'],
            'ground': ['gnd', 'ground', 'vss', 'pgnd', 'agnd', 'dgnd'],
            'mains': ['mains', '230v', '120v', 'ac_', 'line', 'neutral'],
            'communication': ['sda', 'scl', 'i2c', 'spi', 'mosi', 'miso', 'sck', 'rs485', 'can'],
            'high_speed': ['usb', 'dp', 'dm', 'd+', 'd-', 'tx', 'rx', 'pcie', 'hdmi'],
            'rf': ['antenna', 'ant', 'rf_', 'wifi', 'ble', 'lora'],
        }
        
        categorized = {cat: [] for cat in critical_patterns}
        
        for net in nets[:100]:
            name = net.get('name', '').lower()
            for category, patterns in critical_patterns.items():
                if any(p in name for p in patterns):
                    categorized[category].append(net.get('name', ''))
                    break
        
        lines = []
        for category, net_names in categorized.items():
            if net_names:
                lines.append(f"  [{category.upper()}]: {', '.join(net_names[:5])}")
        
        return '\n'.join(lines) if lines else "  (No critical nets detected)"
    
    def _format_key_components(self, components: List[Dict]) -> str:
        """Format key components for context"""
        categories = {
            'MCU/Processor': [],
            'Power ICs': [],
            'Communication': [],
            'Connectors': [],
            'Passives': {'R': 0, 'C': 0, 'L': 0},
        }
        
        for comp in components[:100]:
            ref = comp.get('reference', '')
            value = comp.get('value', '').lower()
            
            if ref.startswith('U') and any(kw in value for kw in ['stm', 'esp', 'pic', 'atm', 'arm', 'mcu']):
                categories['MCU/Processor'].append(f"{ref}: {comp.get('value', '')}")
            elif any(kw in value for kw in ['ldo', 'reg', 'buck', 'boost', '78', '117']):
                categories['Power ICs'].append(f"{ref}: {comp.get('value', '')}")
            elif any(kw in value for kw in ['485', 'can', 'uart', 'usb', 'eth', 'wifi', 'ble']):
                categories['Communication'].append(f"{ref}: {comp.get('value', '')}")
            elif ref.startswith('J') or ref.startswith('P'):
                categories['Connectors'].append(ref)
            elif ref.startswith('R'):
                categories['Passives']['R'] += 1
            elif ref.startswith('C'):
                categories['Passives']['C'] += 1
            elif ref.startswith('L'):
                categories['Passives']['L'] += 1
        
        lines = []
        for cat, items in categories.items():
            if cat == 'Passives':
                lines.append(f"  [{cat}]: R:{items['R']}, C:{items['C']}, L:{items['L']}")
            elif items:
                lines.append(f"  [{cat}]: {', '.join(items[:5])}")
        
        return '\n'.join(lines)
    
    def _format_rule_engine_issues(self, issues: List[Issue]) -> str:
        """Format rule engine issues for context"""
        lines = []
        for issue in issues:
            severity_icon = {'critical': '🔴', 'error': '🟠', 'warning': '🟡', 'info': '🔵'}
            icon = severity_icon.get(issue.severity.value, '⚪')
            lines.append(f"  {icon} [{issue.category}] {issue.title}")
        
        return '\n'.join(lines) if lines else "  (No issues from rule engines)"
    
    def _run_expert_analysis(self, expert_context: str) -> AnalysisResult:
        """Run GPT-4 expert analysis with RAG context"""
        
        system_prompt = self._get_expert_system_prompt()
        user_prompt = self._get_expert_user_prompt(expert_context)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            
            return self._parse_expert_response(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"Expert analysis failed: {e}")
            return AnalysisResult(
                issues=[],
                suggestions=[],
                expert_insights=[],
                standards_applied=[],
                confidence_score=0.0
            )
    
    def _get_expert_system_prompt(self) -> str:
        """Get professional system prompt for expert analysis"""
        return """You are a SENIOR PCB DESIGN ENGINEER with 20+ years of experience in:

🎓 CERTIFICATIONS & EXPERTISE:
• IPC CID+ (Certified Interconnect Designer)
• IPC-2221A/B (Generic Standard on Printed Board Design)
• IPC-2152 (Current Carrying Capacity)
• IEC 62368-1 (Audio/Video/IT Equipment Safety)
• IEC 60601-1 (Medical Electrical Equipment)
• EMC/EMI compliance (FCC Part 15, CE/EN)

🏭 INDUSTRY EXPERIENCE:
• Consumer Electronics (10+ years)
• Industrial Automation & IoT (8+ years)
• Medical Devices (5+ years)
• Automotive Electronics (3+ years)

📋 YOUR ANALYSIS METHODOLOGY:

1. EVIDENCE-BASED FINDINGS
   - Every issue MUST cite specific evidence (component, net, measurement)
   - Reference applicable standards (IPC, IEC, TI app notes)
   - Include quantitative data when available

2. SEVERITY CLASSIFICATION (BE CONSERVATIVE)
   • CRITICAL: Safety hazard OR guaranteed failure
     - Requires: Specific evidence + known failure mode + affected items
     - Example: "U3 (LM1117-3.3) missing input capacitor - causes instability"
   
   • WARNING: Likely performance impact
     - Requires: Evidence + probable failure scenario
     - Example: "RS485 termination R12=100Ω, should be 120Ω per TI SLLA272B"
   
   • INFO: Best practice recommendation
     - General guidance without specific failure risk
     - Example: "Consider thermal vias under U5 QFN package"

3. AVOID THESE COMMON AI MISTAKES:
   ❌ Generic advice without specific evidence
   ❌ Speculating about components not in the design
   ❌ Over-reporting minor issues as critical
   ❌ Repeating issues already found by rule engines
   ❌ Making up component references

4. REQUIRED OUTPUT FORMAT (JSON):
{
  "issues": [
    {
      "severity": "warning",
      "category": "power_supply|safety|bus_interface|thermal|emc_emi|layout|components",
      "title": "Concise issue title",
      "description": "Detailed explanation with SPECIFIC evidence",
      "evidence": ["U3 value=LM1117", "No C near VIN pin"],
      "standard_reference": "IPC-2221A Section 6.3",
      "suggested_fix": "Specific actionable fix",
      "affected_components": ["U3", "C5"],
      "affected_nets": ["VCC_3V3"],
      "confidence": "high|medium|low"
    }
  ],
  "suggestions": [
    {
      "title": "Improvement suggestion",
      "description": "Detailed explanation",
      "benefit": "Reliability|Performance|Cost|EMC",
      "effort": "low|medium|high",
      "priority": "high|medium|low"
    }
  ],
  "expert_insights": [
    {
      "topic": "Topic area",
      "insight": "Expert observation or recommendation",
      "rationale": "Why this matters"
    }
  ],
  "standards_applied": ["IPC-2221A", "IEC 62368-1"],
  "confidence_score": 0.85
}

REMEMBER: Quality over quantity. 3-5 high-quality, evidence-based findings are better than 10 speculative ones."""
    
    def _get_expert_user_prompt(self, expert_context: str) -> str:
        """Get user prompt for expert analysis"""
        return f"""{expert_context}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 YOUR ANALYSIS TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Using the KNOWLEDGE BASE CONTEXT provided above (from IPC standards, TI app notes, etc.),
analyze this PCB design for issues that the automated rule engines may have MISSED.

FOCUS AREAS:
1. Power supply design quality (per TI AN-1229, AN-1149)
2. Communication bus implementation (per NXP AN10216, TI SLLA272B)
3. Safety compliance if mains voltage present (per IEC 62368-1)
4. Thermal management for power components
5. EMC/EMI considerations
6. Component selection and derating

CRITICAL INSTRUCTIONS:
• ONLY report NEW issues not already found by rule engines
• CITE specific components (U1, R5) and nets when reporting issues
• REFERENCE the knowledge base content when applicable
• BE CONSERVATIVE with severity - when uncertain, use lower severity
• Provide EXACTLY 5 actionable suggestions even if few issues found
• Include 2-3 expert insights based on design characteristics

Return your analysis in the specified JSON format."""
    
    def _run_vision_analysis(
        self,
        layout_images: List[str],
        parsed_data: Dict
    ) -> List[Issue]:
        """Analyze layout images using GPT-4 Vision"""
        issues = []
        
        for image_path in layout_images[:3]:  # Limit images
            if not os.path.exists(image_path):
                continue
            
            try:
                # Load and encode image
                with open(image_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
                
                # Determine image type
                ext = Path(image_path).suffix.lower()
                media_type = {
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                }.get(ext, 'image/png')
                
                response = self.client.chat.completions.create(
                    model=self.vision_model,
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a PCB layout review expert. Analyze this PCB layout image for:
1. Component placement issues (thermal concerns, routing bottlenecks)
2. Copper pour quality (islands, thermal relief)
3. Trace routing (right angles, acute angles, bottlenecks)
4. Via placement (excessive vias, via-in-pad issues)
5. Silkscreen/soldermask issues

Return JSON: {"issues": [{"title": "...", "description": "...", "location": "approx location"}]}
Only report VISIBLE issues. If image is unclear, return empty issues array."""
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Analyze this PCB layout image:"},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{media_type};base64,{image_data}",
                                        "detail": "high"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
                
                result = json.loads(response.choices[0].message.content)
                
                for item in result.get('issues', []):
                    issues.append(Issue(
                        issue_code=f"VISION-{hash(item.get('title', ''))%1000:03d}",
                        severity=IssueSeverity.INFO,
                        category="layout_visual",
                        title=f"👁️ Vision: {item.get('title', 'Layout observation')}",
                        description=item.get('description', ''),
                        suggested_fix=item.get('location', 'See layout'),
                        affected_components=[],
                        affected_nets=[]
                    ))
                
            except Exception as e:
                logger.warning(f"Vision analysis failed for {image_path}: {e}")
        
        return issues
    
    def _parse_expert_response(self, response_text: str) -> AnalysisResult:
        """Parse expert response into AnalysisResult"""
        try:
            data = json.loads(response_text)
            
            issues = []
            for item in data.get('issues', []):
                # Map and validate severity
                severity_map = {
                    'critical': IssueSeverity.CRITICAL,
                    'warning': IssueSeverity.WARNING,
                    'info': IssueSeverity.INFO
                }
                
                raw_severity = item.get('severity', 'info').lower()
                confidence = item.get('confidence', 'low')
                
                # Downgrade critical if low confidence
                if raw_severity == 'critical' and confidence != 'high':
                    raw_severity = 'warning'
                    logger.info(f"Downgraded CRITICAL to WARNING: low confidence")
                
                severity = severity_map.get(raw_severity, IssueSeverity.INFO)
                
                issues.append(Issue(
                    issue_code=f"AI-{hash(item.get('title', ''))%1000:03d}",
                    severity=severity,
                    category=item.get('category', 'ai_analysis'),
                    title=f"🤖 {item.get('title', 'AI Finding')}",
                    description=item.get('description', ''),
                    suggested_fix=item.get('suggested_fix', ''),
                    affected_components=item.get('affected_components', []),
                    affected_nets=item.get('affected_nets', []),
                    metadata={
                        'evidence': item.get('evidence', []),
                        'standard_reference': item.get('standard_reference', ''),
                        'confidence': confidence
                    }
                ))
            
            suggestions = data.get('suggestions', [])
            expert_insights = data.get('expert_insights', [])
            standards_applied = data.get('standards_applied', [])
            confidence_score = data.get('confidence_score', 0.5)
            
            return AnalysisResult(
                issues=issues,
                suggestions=suggestions,
                expert_insights=expert_insights,
                standards_applied=standards_applied,
                confidence_score=confidence_score
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse expert response: {e}")
            return AnalysisResult(
                issues=[],
                suggestions=[],
                expert_insights=[],
                standards_applied=[],
                confidence_score=0.0
            )
    
    def _validate_results(
        self,
        result: AnalysisResult,
        existing_issues: List[Issue]
    ) -> AnalysisResult:
        """Validate and filter AI results"""
        
        # Get existing issue titles for deduplication
        existing_titles = set(i.title.lower() for i in existing_issues)
        
        # Filter out duplicates and low-quality issues
        filtered_issues = []
        for issue in result.issues:
            # Check for duplicate
            if issue.title.lower() in existing_titles:
                continue
            
            # Check for generic advice
            if self._is_generic_advice(issue.title, issue.description):
                continue
            
            # Check for evidence
            evidence = issue.metadata.get('evidence', []) if issue.metadata else []
            if issue.severity == IssueSeverity.CRITICAL and not evidence:
                # Downgrade critical without evidence
                issue = Issue(
                    issue_code=issue.issue_code,
                    severity=IssueSeverity.WARNING,
                    category=issue.category,
                    title=issue.title,
                    description=issue.description,
                    suggested_fix=issue.suggested_fix,
                    affected_components=issue.affected_components,
                    affected_nets=issue.affected_nets,
                    metadata=issue.metadata
                )
            
            filtered_issues.append(issue)
        
        return AnalysisResult(
            issues=filtered_issues,
            suggestions=result.suggestions[:5],  # Limit suggestions
            expert_insights=result.expert_insights[:3],  # Limit insights
            standards_applied=result.standards_applied,
            confidence_score=result.confidence_score
        )
    
    def _is_generic_advice(self, title: str, description: str) -> bool:
        """Check if issue is generic advice without specific evidence"""
        generic_patterns = [
            'consider adding',
            'ensure adequate',
            'verify that',
            'check that',
            'make sure',
            'it is recommended',
            'best practice suggests',
            'generally speaking',
        ]
        
        combined = (title + ' ' + description).lower()
        
        # Check for generic patterns without specific references
        for pattern in generic_patterns:
            if pattern in combined:
                # Allow if there are specific component references
                has_specific = any(
                    ref in combined
                    for ref in ['u1', 'u2', 'r1', 'c1', 'd1', 'j1', 'specifically', 'measured']
                )
                if not has_specific:
                    return True
        
        return False
    
    def ask_expert(self, question: str, pcb_context: Optional[Dict] = None) -> str:
        """
        Ask the AI expert a specific question about PCB design
        
        Args:
            question: Natural language question
            pcb_context: Optional PCB context for relevant answers
        
        Returns:
            Expert answer
        """
        if not self.enabled:
            return "AI analysis is not enabled."
        
        # Retrieve relevant knowledge
        rag_context = self.rag.retrieve_for_query(question, top_k=5)
        
        prompt = f"""You are a senior PCB design expert. Answer this question using the provided knowledge base context.

KNOWLEDGE BASE CONTEXT:
{rag_context.context_text[:4000]}

QUESTION: {question}

Provide a clear, technical answer with specific guidance. Reference standards (IPC, IEC, TI app notes) when applicable."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a senior PCB design expert providing technical guidance."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Expert question failed: {e}")
            return f"Unable to answer question: {e}"
