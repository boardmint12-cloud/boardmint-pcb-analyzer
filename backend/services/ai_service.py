"""
AI-powered PCB analysis service using OpenAI GPT-4
Enhances rule engine results with intelligent suggestions
"""
import json
import logging
from typing import List, Dict, Any
from pathlib import Path

from openai import OpenAI
from config import get_settings
from rules.base_rule import Issue, IssueSeverity

logger = logging.getLogger(__name__)


class AIAnalysisService:
    """Service for AI-enhanced PCB analysis"""
    
    def __init__(self):
        settings = get_settings()
        self.enabled = settings.enable_ai_analysis and settings.openai_api_key
        if self.enabled:
            self.client = OpenAI(api_key=settings.openai_api_key)
            self.model = settings.openai_model
            logger.info(f"AI Analysis enabled with model: {self.model}")
        else:
            logger.info("AI Analysis disabled")
    
    def analyze_pcb(
        self,
        project_path: Path,
        parsed_data: Dict[str, Any],
        rule_engine_issues: List[Issue],
        fab_profile: str
    ) -> tuple[List[Issue], List[Dict[str, str]]]:
        """
        Use AI to analyze PCB and suggest additional issues and improvements
        
        Args:
            project_path: Path to extracted project files
            parsed_data: Parsed PCB data (nets, components, board info)
            rule_engine_issues: Issues found by rule engines
            fab_profile: Fabrication profile being used
            
        Returns:
            Tuple of (AI-suggested issues, improvement suggestions)
        """
        if not self.enabled:
            logger.info("AI analysis skipped (disabled)")
            return [], []
        
        try:
            logger.info("Starting AI-enhanced analysis...")
            
            # Build context for AI
            context = self._build_context(parsed_data, rule_engine_issues, fab_profile)
            
            # Get file contents to analyze
            file_contents = self._read_project_files(project_path)
            
            # Create prompt
            prompt = self._create_analysis_prompt(context, file_contents, rule_engine_issues)
            
            # Call OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more focused analysis
                max_tokens=2500,  # Increased for issues + suggestions
                response_format={"type": "json_object"}
            )
            
            # Parse AI response (returns issues and suggestions)
            ai_issues, suggestions = self._parse_ai_response(response.choices[0].message.content)
            logger.info(f"AI found {len(ai_issues)} additional issues and {len(suggestions)} improvement suggestions")
            
            return ai_issues, suggestions
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return [], []
    
    def _build_context(
        self,
        parsed_data: Dict[str, Any],
        rule_engine_issues: List[Issue],
        fab_profile: str
    ) -> str:
        """Build detailed context about the project"""
        
        board_info = parsed_data.get("board_info", {})
        nets = parsed_data.get("nets", [])
        components = parsed_data.get("components", [])
        
        # Categorize issues by severity
        critical_count = sum(1 for i in rule_engine_issues if i.severity == IssueSeverity.CRITICAL)
        warning_count = sum(1 for i in rule_engine_issues if i.severity == IssueSeverity.WARNING)
        
        context = f"""
PROJECT CONTEXT:
================

DOMAIN: Smart Building, Home Automation & Industrial IoT
- Focus: HVAC controllers, lighting systems, access control, environmental sensors, occupancy detection, energy monitoring, wireless IoT nodes
- Environment: Commercial/residential installations, indoor/outdoor deployment
- Requirements: High reliability, long product life (10+ years), low power consumption, wireless connectivity
- Standards: Must comply with electrical safety and EMC/RF regulations (IEC 61010, UL 62368, FCC Part 15, CE/EN)

BOARD INFORMATION:
- Dimensions: {board_info.get('size_x', 'unknown')} x {board_info.get('size_y', 'unknown')} mm
- Layer Count: {board_info.get('layer_count', 'unknown')}
- Total Nets: {len(nets)}
- Total Components: {len(components)}
- Fabrication Profile: {fab_profile}

CRITICAL NETS TO ANALYZE:
{self._identify_critical_nets(nets)}

KEY COMPONENTS:
{self._summarize_components(components)}

RULE ENGINE FINDINGS:
- Critical Issues: {critical_count}
- Warnings: {warning_count}
- Top concerns: {self._summarize_top_issues(rule_engine_issues)}

SMART BUILDING / IoT SPECIFIC CONCERNS:
1. Mains Safety (230VAC): Clearances, isolation, creepage distances, protection
2. Communication Buses: RS-485, CAN bus, I2C, SPI reliability
3. Wireless Communication: Wi-Fi, Zigbee, BLE, LoRa antenna placement and RF layout
4. Power Supply Stability: Regulators, bulk caps, voltage rails, noise filtering
5. Battery Power: Charging circuits, battery protection, low-power modes, power consumption
6. EMC/EMI Compliance: Filtering, grounding, shielding, FCC/CE requirements
7. ESD Protection: TVS diodes, varistors on user-accessible connectors
8. Thermal Management: Component derating, airflow, heat dissipation
9. Long-term Reliability: Component quality, redundancy, MTBF
10. Field Serviceability: Test points, debugging access, LED indicators, remote diagnostics
11. Environmental: Conformal coating, temperature range, humidity, IP rating
12. IoT Security: Secure boot, encryption chips, tamper detection (if applicable)
"""
        return context
    
    def _identify_critical_nets(self, nets: List[Dict]) -> str:
        """Identify and list critical nets"""
        critical_patterns = [
            "230V", "MAINS", "L_IN", "N_IN", "AC",
            "RS485", "CAN", "MODBUS",
            "3V3", "5V", "12V", "24V",
            "RELAY", "OUTPUT",
            "VBAT", "BAT", "BATTERY",
            "WIFI", "ZIGBEE", "BLE", "LORA", "RF",
            "ANTENNA", "ANT",
            "USB", "ETH", "POE"
        ]
        
        critical = []
        for net in nets[:50]:  # Limit to first 50
            name = net.get("name", "")
            for pattern in critical_patterns:
                if pattern in name.upper():
                    critical.append(f"  - {name}: {len(net.get('connections', []))} connections")
                    break
        
        return "\n".join(critical) if critical else "  (No obvious critical nets detected)"
    
    def _summarize_components(self, components: List[Dict]) -> str:
        """Summarize key components"""
        summary = []
        component_types = {}
        
        for comp in components[:100]:  # Limit to first 100
            ref = comp.get("reference", "")
            value = comp.get("value", "")
            
            # Count by type
            prefix = ref[0] if ref else "?"
            component_types[prefix] = component_types.get(prefix, 0) + 1
            
            # Flag key components
            if ref.startswith("U") and any(kw in value.upper() for kw in ["MCU", "MICRO", "STM", "ESP", "ARM"]):
                summary.append(f"  - {ref}: {value} (Microcontroller)")
            elif "RELAY" in value.upper():
                summary.append(f"  - {ref}: {value} (Relay - check flyback!)")
            elif "OPTO" in value.upper() or "817" in value:
                summary.append(f"  - {ref}: {value} (Isolation)")
        
        type_summary = ", ".join([f"{k}:{v}" for k, v in sorted(component_types.items())])
        summary.insert(0, f"Component counts: {type_summary}")
        
        return "\n".join(summary) if summary else "  (No components detected)"
    
    def _summarize_top_issues(self, issues: List[Issue]) -> str:
        """Summarize top issues from rule engine"""
        if not issues:
            return "None found"
        
        categories = {}
        for issue in issues:
            cat = issue.category
            categories[cat] = categories.get(cat, 0) + 1
        
        return ", ".join([f"{k}({v})" for k, v in sorted(categories.items(), key=lambda x: -x[1])])
    
    def _read_project_files(self, project_path: Path) -> str:
        """Read relevant project files for AI analysis"""
        file_contents = []
        
        # Read key files (limit size)
        extensions = [".kicad_pcb", ".kicad_sch", ".csv", ".pos"]
        
        for ext in extensions:
            files = list(project_path.rglob(f"*{ext}"))
            for file_path in files[:3]:  # Max 3 files per type
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    # Truncate large files
                    if len(content) > 10000:
                        content = content[:10000] + "\n... (truncated)"
                    file_contents.append(f"\n=== {file_path.name} ===\n{content}")
                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")
        
        return "\n".join(file_contents) if file_contents else "(No readable files found)"
    
    def _get_system_prompt(self) -> str:
        """Get system prompt defining AI's role"""
        return """You are an expert PCB design reviewer specializing in SMART BUILDING, HOME AUTOMATION, and INDUSTRIAL IoT systems.

Your expertise includes:
- IEC 61010 & UL 61010 (Safety for measurement/control equipment)
- IEC/UL 62368 (IT and audio/video equipment safety)
- RS-485/Modbus and CAN bus design reliability
- Wireless modules (Wi-Fi, Zigbee, BLE, LoRa, NB-IoT) and antenna layout best practices
- Ethernet/PoE interface design and surge protection (IEC 61643)
- Mains voltage safety (230VAC isolation, clearances, creepage distances)
- Low-power and battery-operated device design (power optimization, battery safety)
- EMC/EMI filtering and regulatory compliance (FCC Part 15, CE/EN, IC)
- ESD and surge protection for user-accessible connectors and interfaces
- IoT sensor integration (temperature, humidity, occupancy, air quality)
- Long-term reliability for building automation (10+ year product life)
- Field serviceability and remote diagnostics

Your task: Review PCB designs and identify potential issues that automated rule engines might miss.

Focus on:
1. Design patterns that could cause field failures
2. Communication bus implementation flaws (wired and wireless)
3. Power supply stability and battery power management
4. Wireless antenna placement and RF considerations
5. Thermal management concerns
6. Manufacturing/assembly problems
7. Service and maintenance difficulties
8. Component selection issues
9. EMC/EMI and regulatory compliance risks
10. ESD protection for user-accessible interfaces

CRITICAL SEVERITY GUIDELINES:
- Use critical ONLY if you have STRONG EVIDENCE of a safety hazard or guaranteed failure
- Requires: Specific component or net identified AND known failure mode
- Examples: Missing termination resistor on detected RS-485 bus, no bulk capacitor on switching regulator
- Do NOT use critical for: Generic advice, theoretical issues, could be scenarios

RESPOND IN JSON FORMAT ONLY with this structure:
{
  "issues": [
    {
      "severity": "warning or info",
      "category": "communication_reliability or power_supply_stability or thermal_management or field_serviceability or environmental or wireless_rf or battery_power or emc_emi or esd_protection",
      "title": "Brief issue title",
      "description": "Detailed explanation with SPECIFIC evidence",
      "suggested_fix": "How to fix it",
      "affected_components": ["U1", "R5"],
      "affected_nets": ["RS485_A", "GND"],
      "evidence_quality": "high or medium or low"
    }
  ],
  "suggestions": [
    {
      "title": "Improvement suggestion title",
      "description": "Detailed explanation of the improvement",
      "benefit": "What this would improve (reliability, performance, cost, etc.)",
      "priority": "high or medium or low"
    }
  ]
}

IMPORTANT:
- Be CONSERVATIVE with severity - better to under-report than over-report
- Only report issues you have SPECIFIC EVIDENCE for
- Avoid generic industry advice unless you see the actual problem
- If uncertain, use info severity and explain limitations
- Limit to 5-8 most important issues only
- ALWAYS provide exactly 5 improvement suggestions even if no critical issues found
- Suggestions should be constructive best practices or design optimizations
- Base suggestions on actual design characteristics not generic advice"""
    
    def _create_analysis_prompt(
        self,
        context: str,
        file_contents: str,
        rule_engine_issues: List[Issue]
    ) -> str:
        """Create the analysis prompt"""
        
        # Summarize existing issues to avoid duplicates
        existing_issues = "\n".join([
            f"- [{i.severity.value.upper()}] {i.title}"
            for i in rule_engine_issues[:20]  # First 20
        ])
        
        prompt = f"""{context}

AUTOMATED RULE ENGINE ALREADY FOUND:
{existing_issues}

PROJECT FILES:
{file_contents[:15000]}  

YOUR TASK:
Review this PCB project for SMART BUILDING / HOME IoT use. Identify any **high-impact design issues** that could affect real-world performance, safety, or reliability, especially in building automation contexts (access control, lighting, HVAC, sensor nodes, environmental monitoring, etc.).

Now analyze for:
1. **Subtle design issues** the rule engine can't catch
2. **Context-specific problems** for IoT/smart building environments
3. **Wireless communication issues** (antenna placement, RF interference, coexistence)
4. **Battery power and low-power design** concerns
5. **Integration concerns** between subsystems (sensors, actuators, communication)
6. **Real-world failure modes** from field experience
7. **Manufacturing red flags** that could cause yield issues
8. **EMC/EMI and regulatory compliance** risks (FCC, CE)
9. **ESD protection** for user-accessible interfaces

IMPORTANT:
- Only report **NEW issues** not already caught by the rule engine
- Be specific: cite component references (U1, R5, etc.) and net names for each issue
- Focus on **field-failure risks or safety hazards** (noise, isolation, power faults, communication errors)
- **ALWAYS provide exactly 5 improvement suggestions** (best practices or design optimizations) even if no critical issues are found
- Avoid generic advice unrelated to this design; base findings on the given data
- **Do not speculate beyond the provided information**; if unsure, frame it as a possible improvement rather than a definite flaw
- Consider the 10+ year product lifecycle for building automation
- Think about harsh environments (temperature extremes, EMI, power surges, humidity)

Provide your analysis in JSON format with both 'issues' and 'suggestions' arrays."""
        
        return prompt
    
    def _parse_ai_response(self, response_text: str) -> tuple[List[Issue], List[Dict[str, str]]]:
        """Parse AI JSON response into Issue objects and suggestions with validation"""
        try:
            data = json.loads(response_text)
            issues = []
            suggestions = []
            
            # Parse issues
            for item in data.get("issues", []):
                # Map severity string to enum
                severity_map = {
                    "critical": IssueSeverity.CRITICAL,
                    "warning": IssueSeverity.WARNING,
                    "info": IssueSeverity.INFO
                }
                requested_severity = severity_map.get(item.get("severity", "info").lower(), IssueSeverity.INFO)
                
                # Validate CRITICAL severity - downgrade if insufficient evidence
                final_severity = self._validate_severity(
                    requested_severity,
                    item.get("evidence_quality", "low"),
                    item.get("description", ""),
                    item.get("affected_components", []),
                    item.get("affected_nets", [])
                )
                
                # Skip generic/low-value issues
                if self._is_generic_advice(item.get("title", ""), item.get("description", "")):
                    logger.info(f"Skipping generic AI advice: {item.get('title', '')}")
                    continue
                
                issue = Issue(
                    issue_code=f"AI-{hash(item.get('title', ''))% 1000:03d}",  # Generate unique code
                    severity=final_severity,
                    category=item.get("category", "ai_insight"),
                    title=f"🤖 AI: {item.get('title', 'Unknown issue')}",
                    description=item.get("description", ""),
                    suggested_fix=item.get("suggested_fix", ""),
                    affected_components=item.get("affected_components", []),
                    affected_nets=item.get("affected_nets", []),
                    location_x=None,
                    location_y=None,
                    layer=None
                )
                issues.append(issue)
            
            # Parse suggestions
            for suggestion in data.get("suggestions", []):
                suggestions.append({
                    "title": suggestion.get("title", ""),
                    "description": suggestion.get("description", ""),
                    "benefit": suggestion.get("benefit", ""),
                    "priority": suggestion.get("priority", "medium")
                })
            
            logger.info(f"AI generated {len(issues)} validated issues (filtered from {len(data.get('issues', []))}) and {len(suggestions)} suggestions")
            return issues, suggestions
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response was: {response_text[:500]}")
            return [], []
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return [], []
    
    def _validate_severity(
        self,
        requested: IssueSeverity,
        evidence_quality: str,
        description: str,
        components: List[str],
        nets: List[str]
    ) -> IssueSeverity:
        """
        Validate and potentially downgrade severity
        
        CRITICAL requires:
        - High evidence quality
        - Specific affected components or nets
        - Concrete failure mode described
        """
        if requested != IssueSeverity.CRITICAL:
            return requested
        
        # Downgrade CRITICAL if insufficient evidence
        if evidence_quality.lower() not in ["high"]:
            logger.warning(f"Downgrading CRITICAL to WARNING: insufficient evidence ({evidence_quality})")
            return IssueSeverity.WARNING
        
        if not components and not nets:
            logger.warning(f"Downgrading CRITICAL to WARNING: no specific affected items")
            return IssueSeverity.WARNING
        
        # Check for vague language
        vague_phrases = ["may", "might", "could", "potentially", "possibly", "likely"]
        if any(phrase in description.lower() for phrase in vague_phrases):
            logger.warning(f"Downgrading CRITICAL to WARNING: contains uncertainty language")
            return IssueSeverity.WARNING
        
        return IssueSeverity.CRITICAL
    
    def _is_generic_advice(self, title: str, description: str) -> bool:
        """
        Filter out generic industry advice that doesn't apply to specific design
        """
        generic_patterns = [
            "consider adding conformal coating",
            "ensure conformal coating",
            "conformal coating compatibility",
            "add test points for",
            "consider adding test points",
            "ensure adequate",
            "verify that",
            "check that",
            "make sure"
        ]
        
        combined = (title + " " + description).lower()
        
        # If it's purely generic advice without specifics
        for pattern in generic_patterns:
            if pattern in combined:
                # Check if there are actual specific components/nets mentioned
                has_specifics = any(ref in combined for ref in ["U", "R", "C", "D", "J", "Q"])
                if not has_specifics:
                    return True
        
        return False
