# Author: Yohan Hmaiti — University of Central Florida
# ---------------------------------------------------------------------
# Local CVEfixes dataset loader that reads from folder structure.
# Each CVE has vulnerable (code_before) and fixed (code_after) versions.


from pathlib import Path
import re
from tqdm import tqdm

def load_cvefixes_dataset(source_path: str = "../data/CVE_Dataset/cve_code_files"):
    """
        Load CVEfixes dataset from local folder structure.
        
        Args:
            source_path (str): Path to the folder containing CVE subfolders
            
        Returns:
            list[dict]: List of samples with structure:
                {
                    "id": int,
                    "cve_id": str,
                    "file_number": int,
                    "filename": str,
                    "language": str,
                    "code": str,
                    "label": str  # "VULNERABLE" or "SAFE"
                }
        
        Notes:
            - Each CVE folder contains before/after file pairs
            - code_before → VULNERABLE samples
            - code_after → SAFE samples
            - Language inferred from file extension
        """
        
    extension_to_language = {
            '.c': 'C',
            '.cpp': 'C++', '.cc': 'C++', '.cxx': 'C++', '.h': 'C++', '.hpp': 'C++',
            '.java': 'Java',
            '.py': 'Python',
            '.js': 'JavaScript', '.jsx': 'JavaScript',
            '.ts': 'TypeScript', '.tsx': 'TypeScript',
            '.go': 'Go',
            '.rs': 'Rust',
            '.php': 'PHP',
            '.rb': 'Ruby',
            '.cs': 'C#',
            '.swift': 'Swift',
            '.kt': 'Kotlin',
            '.scala': 'Scala',
            '.sh': 'Shell',
            '.sql': 'SQL',
            '.html': 'HTML',
            '.css': 'CSS'
    }
        
    def infer_language(filename: str) -> str:
        if not filename or filename == "unknown":
                return "unknown"
        ext = Path(filename).suffix.lower()
        return extension_to_language.get(ext, "unknown")
        
    samples = []
    sample_id = 0
    source_dir = Path(source_path)
    
    if not source_dir.exists():
        raise ValueError(f"CVEfixes source path does not exist: {source_path}")
    
    cve_folders = sorted([f for f in source_dir.iterdir() if f.is_dir()])
    
    for cve_folder in tqdm(cve_folders, desc="Loading CVEfixes samples", unit="CVE"):
        cve_id = cve_folder.name
        readme_path = cve_folder / "README.txt"
        original_filenames = {}
        
        if readme_path.exists():
            readme_content = readme_path.read_text(encoding='utf-8')
            for line in readme_content.split('\n'):
                match = re.match(r'\s+(\d+)\.\s+(.+)', line)
                if match:
                    file_num = int(match.group(1))
                    filename = match.group(2).strip()
                    original_filenames[file_num] = filename
        
        before_files = sorted(cve_folder.glob('*_before_*.txt'))
        
        for before_file in before_files:
            match = re.match(r'(\d+)_before_', before_file.name)
            if not match:
                continue
            
            file_num = int(match.group(1))
            after_file = cve_folder / before_file.name.replace('_before_', '_after_')
            filename = original_filenames.get(file_num, "unknown")
            language = infer_language(filename)
            
            try:
                code_before = before_file.read_text(encoding='utf-8')
                if code_before:
                    samples.append({
                        "id": sample_id,
                        "cve_id": cve_id,
                        "file_number": file_num,
                        "filename": filename,
                        "language": language,
                        "code": code_before,
                        "label": "VULNERABLE"
                    })
                    sample_id += 1
            except Exception:
                pass
            
            try:
                if after_file.exists():
                    code_after = after_file.read_text(encoding='utf-8')
                    if code_after:
                        samples.append({
                            "id": sample_id,
                            "cve_id": cve_id,
                            "file_number": file_num,
                            "filename": filename,
                            "language": language,
                            "code": code_after,
                            "label": "SAFE"
                        })
                        sample_id += 1
            except Exception:
                pass
    
    return samples


dataset = load_cvefixes_dataset("../data/CVE_Dataset/cve_code_files/")

print(f"Total samples: {len(dataset):,}")
print(f"Vulnerable samples: {sum(1 for s in dataset if s['label'] == 'VULNERABLE'):,}")
print(f"Safe samples: {sum(1 for s in dataset if s['label'] == 'SAFE'):,}")
print(f"\nLanguages: {set(s['language'] for s in dataset)}")
print(f"\nFirst sample: {dataset[0]}")