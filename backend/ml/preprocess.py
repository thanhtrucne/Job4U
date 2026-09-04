import re
import unicodedata

def clean_text(text: str) -> str:
    """
    Clean text for ML processing:
    - Normalization
    - Lowercase
    - Remove special characters and numbers
    - Strip whitespace
    """
    if not text:
        return ""
    
    # Normalize unicode
    text = unicodedata.normalize('NFC', text)
    
    # Lowercase
    text = text.lower()
    
    # Remove HTML tags if any
    text = re.sub(r'<.*?>', ' ', text)
    
    # Remove URLs
    text = re.sub(r'http\S+|www\S+|https\S+', ' ', text, flags=re.MULTILINE)
    
    # Remove email addresses
    text = re.sub(r'\S*@\S*\s?', ' ', text)
    
    # Remove special characters and numbers
    # Keep only Vietnamese letters and spaces
    text = re.sub(r'[^a-zA-Zàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ\s]', ' ', text)
    
    # Remove extra whitespaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def tokenize(text: str) -> list:
    """
    Simple whitespace tokenization. 
    Can be expanded with specialized Vietnamese tokenizers if needed.
    """
    return text.split()
