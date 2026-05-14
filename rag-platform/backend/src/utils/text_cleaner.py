import re
from typing import Optional


def clean_document_text(text: Optional[str]) -> str:
    """
    清理文档文本，去除多余空行、空格和特殊字符，保持段落结构
    
    清理步骤：
    1. 统一换行符为\n，处理Windows风格的\r\n和旧Mac风格的\r
    2. 移除段落内部的换行（单个换行，前后都是非换行字符），替换为空格
    3. 将 2 个以上连续换行符替换为 2 个（保留段落之间的一个空行）
    4. 移除每行首尾的空格
    5. 统一多个空格为单个空格
    6. 去除首尾的空白字符
    
    Args:
        text: 待清理的原始文本
        
    Returns:
        清理后的整洁文本
    """
    if not text:
        return ""
    
    cleaned_text = text
    
    # 1. 统一换行符为\n，处理Windows风格的\r\n和旧Mac风格的\r
    cleaned_text = cleaned_text.replace('\r\n', '\n').replace('\r', '\n')
    
    # 2. 移除段落内部的换行（单个换行，前后都是非换行字符），替换为空格
    cleaned_text = re.sub(r'(?<=[^\n])\n(?=[^\n])', ' ', cleaned_text)
    
    # 3. 将 2 个以上连续换行符替换为 2 个（保留段落之间的一个空行）
    cleaned_text = re.sub(r"\n{2,}", "\n\n", cleaned_text)
    
    # 4. 移除每行首尾的空格
    lines = cleaned_text.split('\n')
    lines = [line.strip() for line in lines]
    cleaned_text = '\n'.join(lines)
    
    # 5. 统一多个空格为单个空格
    cleaned_text = re.sub(r' +', ' ', cleaned_text)
    
    # 6. 去除首尾的空白字符
    cleaned_text = cleaned_text.strip()
    
    return cleaned_text
