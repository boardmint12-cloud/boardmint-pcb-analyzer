"""
Advanced file loader - extracts and flattens all files from uploaded ZIP
"""
import logging
import zipfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class FileLoader:
    """Load and organize all files from PCB project ZIP"""
    
    def __init__(self):
        self.supported_extensions = {
            'pcb': ['.kicad_pcb', '.kicad_pcb-bak'],
            'schematic': ['.kicad_sch', '.sch', '.bak'],
            'netlist': ['.net'],
            'bom': ['.csv', '.xml'],
            'position': ['.pos'],
            'footprint': ['.kicad_mod'],
            'library': ['.lib', '.dcm'],
            'project': ['.kicad_pro', '.pro'],
            'table': ['fp-lib-table', 'sym-lib-table'],
            'image': ['.jpg', '.jpeg', '.png', '.pdf']
        }
    
    def extract_and_flatten(self, zip_path: Path, extract_to: Path) -> Dict[str, List[Path]]:
        """
        Extract ZIP and organize files by type
        Flattens nested folders - all files accessible in one place
        
        Args:
            zip_path: Path to uploaded ZIP file
            extract_to: Directory to extract to
            
        Returns:
            Dict mapping file types to list of file paths
        """
        logger.info(f"Extracting ZIP: {zip_path}")
        
        # Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        
        # Collect all files recursively
        all_files = self._collect_files(extract_to)
        
        # Organize by type
        organized = self._organize_by_type(all_files)
        
        logger.info(f"Organized files: {[(k, len(v)) for k, v in organized.items()]}")
        
        return organized
    
    def _collect_files(self, directory: Path) -> List[Path]:
        """Recursively collect all files, filter out junk"""
        files = []
        
        for path in directory.rglob('*'):
            if path.is_file():
                # Filter out macOS metadata and temp files
                if (path.name.startswith('._') or 
                    '__MACOSX' in str(path) or
                    path.name.startswith('.DS_Store')):
                    continue
                files.append(path)
        
        logger.info(f"Collected {len(files)} files")
        return files
    
    def _organize_by_type(self, files: List[Path]) -> Dict[str, List[Path]]:
        """Organize files by their type/purpose"""
        organized = {}
        
        for file_path in files:
            file_type = self._identify_file_type(file_path)
            if file_type:
                if file_type not in organized:
                    organized[file_type] = []
                organized[file_type].append(file_path)
        
        return organized
    
    def _identify_file_type(self, file_path: Path) -> str:
        """Identify what type of file this is"""
        name_lower = file_path.name.lower()
        suffix_lower = file_path.suffix.lower()
        
        # Check each category
        for file_type, extensions in self.supported_extensions.items():
            for ext in extensions:
                if suffix_lower == ext.lower() or name_lower.endswith(ext.lower()):
                    return file_type
        
        return 'other'
    
    def load_file_contents(self, file_path: Path, max_size: int = 5_000_000) -> Tuple[str, bool]:
        """
        Load file contents as text
        
        Args:
            file_path: Path to file
            max_size: Maximum file size to load (default 5MB)
            
        Returns:
            (content, is_binary) tuple
        """
        try:
            if file_path.stat().st_size > max_size:
                logger.warning(f"File too large, truncating: {file_path}")
                return "", True
            
            # Try to read as text
            try:
                content = file_path.read_text(encoding='utf-8')
                return content, False
            except UnicodeDecodeError:
                # Binary file
                return f"[Binary file: {file_path.name}]", True
                
        except Exception as e:
            logger.error(f"Failed to load file {file_path}: {e}")
            return "", True
    
    def prepare_for_gpt(self, organized_files: Dict[str, List[Path]]) -> Dict[str, any]:
        """
        Prepare file contents for GPT processing
        
        Args:
            organized_files: Files organized by type
            
        Returns:
            Dict with file contents ready for GPT
        """
        prepared = {
            'pcb_files': [],
            'schematic_files': [],
            'netlist_files': [],
            'bom_files': [],
            'footprint_files': [],
            'project_config': [],
            'summary': {}
        }
        
        # Load PCB files
        for pcb_file in organized_files.get('pcb', []):
            content, is_binary = self.load_file_contents(pcb_file)
            if not is_binary:
                prepared['pcb_files'].append({
                    'filename': pcb_file.name,
                    'path': str(pcb_file),
                    'content': content,
                    'size': len(content)
                })
        
        # Load schematic files
        for sch_file in organized_files.get('schematic', []):
            content, is_binary = self.load_file_contents(sch_file)
            if not is_binary:
                prepared['schematic_files'].append({
                    'filename': sch_file.name,
                    'path': str(sch_file),
                    'content': content,
                    'size': len(content)
                })
        
        # Load netlist
        for net_file in organized_files.get('netlist', []):
            content, is_binary = self.load_file_contents(net_file)
            if not is_binary:
                prepared['netlist_files'].append({
                    'filename': net_file.name,
                    'path': str(net_file),
                    'content': content,
                    'size': len(content)
                })
        
        # Load BOM
        for bom_file in organized_files.get('bom', []):
            content, is_binary = self.load_file_contents(bom_file)
            if not is_binary:
                prepared['bom_files'].append({
                    'filename': bom_file.name,
                    'path': str(bom_file),
                    'content': content,
                    'size': len(content)
                })
        
        # Load footprints (limit to first 10 to save tokens)
        for fp_file in organized_files.get('footprint', [])[:10]:
            content, is_binary = self.load_file_contents(fp_file)
            if not is_binary:
                prepared['footprint_files'].append({
                    'filename': fp_file.name,
                    'path': str(fp_file),
                    'content': content[:5000],  # Truncate footprints
                    'size': len(content)
                })
        
        # Load project config
        for proj_file in organized_files.get('project', []):
            content, is_binary = self.load_file_contents(proj_file)
            if not is_binary:
                prepared['project_config'].append({
                    'filename': proj_file.name,
                    'content': content
                })
        
        # Create summary
        prepared['summary'] = {
            'total_pcb_files': len(organized_files.get('pcb', [])),
            'total_schematic_files': len(organized_files.get('schematic', [])),
            'total_netlist_files': len(organized_files.get('netlist', [])),
            'total_bom_files': len(organized_files.get('bom', [])),
            'total_footprints': len(organized_files.get('footprint', [])),
            'has_images': len(organized_files.get('image', [])) > 0
        }
        
        logger.info(f"Prepared files for GPT: {prepared['summary']}")
        
        return prepared
