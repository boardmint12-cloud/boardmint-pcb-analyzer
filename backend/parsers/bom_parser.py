"""
BOM (Bill of Materials) Parser
Parses CSV and Excel BOM files with intelligent column detection

Supports various BOM formats from:
- KiCad
- Altium
- Eagle
- OrCAD
- Generic CSV/Excel
"""

import csv
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Try to import openpyxl for Excel support
try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
    logger.warning("openpyxl not installed - Excel BOM support disabled")


@dataclass
class BOMItem:
    """Single BOM line item"""
    reference: str
    value: str
    footprint: str = ""
    quantity: int = 1
    mpn: str = ""  # Manufacturer Part Number
    manufacturer: str = ""
    description: str = ""
    supplier: str = ""
    supplier_pn: str = ""
    dnp: bool = False  # Do Not Populate
    
    # Additional fields
    extra_fields: Dict[str, str] = field(default_factory=dict)


@dataclass
class BOMData:
    """Parsed BOM data"""
    items: List[BOMItem]
    total_unique_parts: int
    total_placements: int
    dnp_count: int
    source_format: str
    warnings: List[str] = field(default_factory=list)


class BOMParser:
    """
    Intelligent BOM parser with automatic column detection
    
    Detects columns for:
    - Reference designators (can be comma-separated)
    - Value/Part Value
    - Footprint/Package
    - Quantity
    - MPN (Manufacturer Part Number)
    - Manufacturer
    - Description
    - DNP (Do Not Populate) markers
    """
    
    # Column name patterns for detection
    COLUMN_PATTERNS = {
        'reference': [
            r'^ref', r'^designator', r'^refdes', r'^reference',
            r'^part.*ref', r'^component', r'^item'
        ],
        'value': [
            r'^value', r'^part.*value', r'^val$', r'^nominal'
        ],
        'footprint': [
            r'^footprint', r'^package', r'^pkg', r'^fp$',
            r'^pattern', r'^pcb.*footprint'
        ],
        'quantity': [
            r'^qty', r'^quantity', r'^count', r'^num'
        ],
        'mpn': [
            r'^mpn', r'^mfr.*p', r'^mfg.*p', r'^manufacturer.*part',
            r'^part.*num', r'^p/n', r'^pn$'
        ],
        'manufacturer': [
            r'^mfr$', r'^mfg$', r'^manufacturer', r'^vendor',
            r'^make$', r'^brand'
        ],
        'description': [
            r'^desc', r'^comment', r'^note', r'^remark'
        ],
        'dnp': [
            r'^dnp', r'^do.*not.*pop', r'^exclude', r'^fitted'
        ],
        'supplier': [
            r'^supplier', r'^distributor', r'^source'
        ],
        'supplier_pn': [
            r'^supplier.*p', r'^dist.*p', r'^order.*num',
            r'^digikey', r'^mouser', r'^lcsc', r'^jlc'
        ],
    }
    
    def __init__(self):
        """Initialize parser"""
        self.column_map: Dict[str, int] = {}
    
    def parse(self, file_path: str) -> BOMData:
        """
        Parse BOM file (CSV or Excel)
        
        Args:
            file_path: Path to BOM file
            
        Returns:
            BOMData with parsed items
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"BOM file not found: {file_path}")
            return BOMData(
                items=[],
                total_unique_parts=0,
                total_placements=0,
                dnp_count=0,
                source_format='unknown',
                warnings=['File not found']
            )
        
        ext = file_path.suffix.lower()
        
        if ext in ('.xlsx', '.xls'):
            return self._parse_excel(file_path)
        else:
            return self._parse_csv(file_path)
    
    def _parse_csv(self, file_path: Path) -> BOMData:
        """Parse CSV BOM file"""
        logger.info(f"Parsing CSV BOM: {file_path}")
        
        items = []
        warnings = []
        
        try:
            # Detect encoding and delimiter
            encoding = self._detect_encoding(file_path)
            
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                # Try to detect delimiter
                sample = f.read(4096)
                f.seek(0)
                
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                reader = csv.reader(f, dialect)
                
                rows = list(reader)
                
            if not rows:
                return BOMData(
                    items=[], total_unique_parts=0, total_placements=0,
                    dnp_count=0, source_format='csv', warnings=['Empty file']
                )
            
            # Find header row (first row with recognizable columns)
            header_row_idx = self._find_header_row(rows)
            
            if header_row_idx < 0:
                warnings.append("Could not detect header row - using first row")
                header_row_idx = 0
            
            # Map columns
            headers = rows[header_row_idx]
            self._map_columns(headers)
            
            if 'reference' not in self.column_map:
                warnings.append("Could not detect reference column")
            
            # Parse data rows
            for row_idx, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 2):
                if not any(cell.strip() for cell in row):
                    continue  # Skip empty rows
                
                try:
                    item = self._parse_row(row)
                    if item:
                        items.append(item)
                except Exception as e:
                    warnings.append(f"Row {row_idx}: {e}")
            
        except Exception as e:
            logger.error(f"CSV parse error: {e}")
            warnings.append(f"Parse error: {e}")
        
        return self._build_result(items, 'csv', warnings)
    
    def _parse_excel(self, file_path: Path) -> BOMData:
        """Parse Excel BOM file"""
        logger.info(f"Parsing Excel BOM: {file_path}")
        
        if not HAS_OPENPYXL:
            return BOMData(
                items=[], total_unique_parts=0, total_placements=0,
                dnp_count=0, source_format='excel',
                warnings=['openpyxl not installed - cannot parse Excel files']
            )
        
        items = []
        warnings = []
        
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            ws = wb.active
            
            rows = []
            for row in ws.iter_rows(values_only=True):
                rows.append([str(cell) if cell is not None else '' for cell in row])
            
            wb.close()
            
            if not rows:
                return BOMData(
                    items=[], total_unique_parts=0, total_placements=0,
                    dnp_count=0, source_format='excel', warnings=['Empty file']
                )
            
            # Find header row
            header_row_idx = self._find_header_row(rows)
            
            if header_row_idx < 0:
                warnings.append("Could not detect header row")
                header_row_idx = 0
            
            # Map columns
            headers = rows[header_row_idx]
            self._map_columns(headers)
            
            # Parse data rows
            for row_idx, row in enumerate(rows[header_row_idx + 1:], start=header_row_idx + 2):
                if not any(str(cell).strip() for cell in row):
                    continue
                
                try:
                    item = self._parse_row(row)
                    if item:
                        items.append(item)
                except Exception as e:
                    warnings.append(f"Row {row_idx}: {e}")
            
        except Exception as e:
            logger.error(f"Excel parse error: {e}")
            warnings.append(f"Parse error: {e}")
        
        return self._build_result(items, 'excel', warnings)
    
    def _detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding"""
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    f.read(1000)
                return encoding
            except UnicodeDecodeError:
                continue
        
        return 'utf-8'
    
    def _find_header_row(self, rows: List[List[str]]) -> int:
        """Find the header row by looking for known column names"""
        best_score = 0
        best_row = -1
        
        for idx, row in enumerate(rows[:10]):  # Check first 10 rows
            score = 0
            row_lower = [str(cell).lower() for cell in row]
            
            for col_type, patterns in self.COLUMN_PATTERNS.items():
                for cell in row_lower:
                    for pattern in patterns:
                        if re.search(pattern, cell):
                            score += 1
                            break
            
            if score > best_score:
                best_score = score
                best_row = idx
        
        return best_row
    
    def _map_columns(self, headers: List[str]):
        """Map column indices to field names"""
        self.column_map = {}
        headers_lower = [str(h).lower().strip() for h in headers]
        
        for col_type, patterns in self.COLUMN_PATTERNS.items():
            for idx, header in enumerate(headers_lower):
                for pattern in patterns:
                    if re.search(pattern, header):
                        if col_type not in self.column_map:
                            self.column_map[col_type] = idx
                        break
        
        logger.debug(f"Column mapping: {self.column_map}")
    
    def _parse_row(self, row: List[str]) -> Optional[BOMItem]:
        """Parse a single BOM row"""
        def get_cell(col_type: str) -> str:
            idx = self.column_map.get(col_type)
            if idx is not None and idx < len(row):
                return str(row[idx]).strip()
            return ''
        
        # Get reference - required field
        reference = get_cell('reference')
        if not reference:
            return None
        
        # Parse quantity
        qty_str = get_cell('quantity')
        try:
            quantity = int(float(qty_str)) if qty_str else 1
        except ValueError:
            quantity = 1
        
        # Check DNP
        dnp_str = get_cell('dnp').lower()
        dnp = dnp_str in ('yes', 'true', '1', 'dnp', 'x', 'excluded')
        
        # Handle comma-separated references (grouped BOM)
        refs = [r.strip() for r in reference.split(',')]
        if len(refs) > 1:
            quantity = len(refs)
            reference = refs[0]  # Use first as primary
        
        return BOMItem(
            reference=reference,
            value=get_cell('value'),
            footprint=get_cell('footprint'),
            quantity=quantity,
            mpn=get_cell('mpn'),
            manufacturer=get_cell('manufacturer'),
            description=get_cell('description'),
            supplier=get_cell('supplier'),
            supplier_pn=get_cell('supplier_pn'),
            dnp=dnp,
            extra_fields={
                'all_references': ','.join(refs) if len(refs) > 1 else reference
            }
        )
    
    def _build_result(
        self,
        items: List[BOMItem],
        source_format: str,
        warnings: List[str]
    ) -> BOMData:
        """Build final result with statistics"""
        total_placements = sum(item.quantity for item in items)
        dnp_count = sum(item.quantity for item in items if item.dnp)
        
        return BOMData(
            items=items,
            total_unique_parts=len(items),
            total_placements=total_placements,
            dnp_count=dnp_count,
            source_format=source_format,
            warnings=warnings
        )


class PickAndPlaceParser:
    """
    Parser for Pick-and-Place / Centroid files
    
    Supports formats from:
    - KiCad (.pos)
    - Altium (.csv, .txt)
    - Eagle (.mnt)
    - Generic XY files
    """
    
    COLUMN_PATTERNS = {
        'reference': [
            r'^ref', r'^designator', r'^part', r'^component'
        ],
        'x': [
            r'^x$', r'^pos.*x', r'^center.*x', r'^mid.*x', r'^location.*x'
        ],
        'y': [
            r'^y$', r'^pos.*y', r'^center.*y', r'^mid.*y', r'^location.*y'
        ],
        'rotation': [
            r'^rot', r'^angle', r'^orient'
        ],
        'side': [
            r'^side', r'^layer', r'^tb$', r'^top.*bot'
        ],
        'value': [
            r'^value', r'^val$'
        ],
        'footprint': [
            r'^footprint', r'^package', r'^pattern'
        ],
    }
    
    def __init__(self):
        """Initialize parser"""
        self.column_map: Dict[str, int] = {}
        self.units = 'mm'  # Default
        self.scale = 1.0
    
    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Parse pick-and-place file
        
        Args:
            file_path: Path to PnP file
            
        Returns:
            List of placement dictionaries
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"PnP file not found: {file_path}")
            return []
        
        logger.info(f"Parsing Pick-and-Place: {file_path}")
        
        try:
            # Read and detect format
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            # Check for KiCad format
            if '# Ref' in content or 'Ref,' in content:
                return self._parse_kicad_pos(content)
            
            # Generic CSV parsing
            return self._parse_generic(file_path)
            
        except Exception as e:
            logger.error(f"PnP parse error: {e}")
            return []
    
    def _parse_kicad_pos(self, content: str) -> List[Dict[str, Any]]:
        """Parse KiCad .pos file format"""
        placements = []
        
        lines = content.strip().split('\n')
        
        # Find units
        for line in lines:
            if 'unit' in line.lower():
                if 'mm' in line.lower():
                    self.scale = 1.0
                elif 'mil' in line.lower() or 'inch' in line.lower():
                    self.scale = 0.0254 if 'mil' in line.lower() else 25.4
        
        # Skip header lines
        data_start = 0
        for idx, line in enumerate(lines):
            if line.startswith('# Ref') or (not line.startswith('#') and ',' in line):
                data_start = idx + 1 if line.startswith('#') else idx
                break
        
        for line in lines[data_start:]:
            if not line.strip() or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) >= 4:
                try:
                    placements.append({
                        'reference': parts[0],
                        'value': parts[1] if len(parts) > 4 else '',
                        'footprint': parts[2] if len(parts) > 4 else parts[1],
                        'x_mm': float(parts[-4 if len(parts) > 4 else -3]) * self.scale,
                        'y_mm': float(parts[-3 if len(parts) > 4 else -2]) * self.scale,
                        'rotation_deg': float(parts[-2 if len(parts) > 4 else -1]),
                        'side': parts[-1] if len(parts) > 4 else 'top'
                    })
                except (ValueError, IndexError):
                    continue
        
        return placements
    
    def _parse_generic(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse generic CSV pick-and-place file"""
        placements = []
        
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            # Detect delimiter
            sample = f.read(4096)
            f.seek(0)
            
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
            except:
                dialect = csv.excel
            
            reader = csv.reader(f, dialect)
            rows = list(reader)
        
        if not rows:
            return []
        
        # Find header and map columns
        header_idx = self._find_header_row(rows)
        if header_idx < 0:
            header_idx = 0
        
        self._map_columns(rows[header_idx])
        
        # Parse data
        for row in rows[header_idx + 1:]:
            if not any(cell.strip() for cell in row):
                continue
            
            placement = self._parse_pnp_row(row)
            if placement:
                placements.append(placement)
        
        return placements
    
    def _find_header_row(self, rows: List[List[str]]) -> int:
        """Find header row"""
        for idx, row in enumerate(rows[:10]):
            row_text = ' '.join(str(c).lower() for c in row)
            if any(re.search(p, row_text) for p in self.COLUMN_PATTERNS['reference']):
                if any(re.search(p, row_text) for p in self.COLUMN_PATTERNS['x']):
                    return idx
        return 0
    
    def _map_columns(self, headers: List[str]):
        """Map columns"""
        self.column_map = {}
        headers_lower = [str(h).lower().strip() for h in headers]
        
        for col_type, patterns in self.COLUMN_PATTERNS.items():
            for idx, header in enumerate(headers_lower):
                for pattern in patterns:
                    if re.search(pattern, header):
                        if col_type not in self.column_map:
                            self.column_map[col_type] = idx
                        break
    
    def _parse_pnp_row(self, row: List[str]) -> Optional[Dict[str, Any]]:
        """Parse single PnP row"""
        def get_cell(col_type: str, default=''):
            idx = self.column_map.get(col_type)
            if idx is not None and idx < len(row):
                return str(row[idx]).strip()
            return default
        
        reference = get_cell('reference')
        if not reference:
            return None
        
        try:
            x = float(get_cell('x', '0'))
            y = float(get_cell('y', '0'))
            rotation = float(get_cell('rotation', '0'))
        except ValueError:
            return None
        
        side = get_cell('side', 'top').lower()
        if 'bot' in side or 'back' in side or side == 'b':
            side = 'bottom'
        else:
            side = 'top'
        
        return {
            'reference': reference,
            'value': get_cell('value'),
            'footprint': get_cell('footprint'),
            'x_mm': x,
            'y_mm': y,
            'rotation_deg': rotation,
            'side': side
        }


def parse_bom(file_path: str) -> BOMData:
    """Convenience function to parse BOM"""
    parser = BOMParser()
    return parser.parse(file_path)


def parse_pnp(file_path: str) -> List[Dict[str, Any]]:
    """Convenience function to parse Pick-and-Place"""
    parser = PickAndPlaceParser()
    return parser.parse(file_path)
