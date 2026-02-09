import os
import shutil
from typing import List, Dict, Any
import PyPDF2

class FileSystemOperations:
    async def read_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Read content from multiple files"""
        results = []
        
        for path in file_paths:
            try:
                content = self.read_file(path)
                results.append({
                    "path": path,
                    "content": content,
                    "success": True
                })
            except Exception as e:
                results.append({
                    "path": path,
                    "error": str(e),
                    "success": False
                })
        
        return results
    
    def read_file(self, path: str) -> str:
        """Read single file based on extension"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"File not found: {path}")
            
        ext = os.path.splitext(path)[1].lower()
        
        if ext == '.pdf':
            return self.read_pdf(path)
        elif ext == '.txt' or ext == '.md' or ext == '.ts' or ext == '.js' or ext == '.py':
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    
    def read_pdf(self, path: str) -> str:
        """Extract text from PDF"""
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
    
    def copy_files(self, source_paths: List[str], dest_dir: str):
        """Copy files to destination directory"""
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        for path in source_paths:
            shutil.copy2(path, dest_dir)
        return f"Copied {len(source_paths)} files to {dest_dir}"
