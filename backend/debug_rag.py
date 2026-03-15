from src.service.rag_service import rag_service
from src.service.document_manager import document_manager

print(f"索引是否存在: {rag_service.index is not None}")
if rag_service.index:
    print(f"文档数量: {len(rag_service.index.docstore.docs)}")

docs = document_manager.get_all_documents()
print(f"已注册文档: {[d.file_name for d in docs]}")
print(f"文档状态: {[(d.file_name, d.status) for d in docs]}")

# 检查PDF文件是否被正确索引
pdf_docs = [d for d in docs if d.file_name.lower().endswith(".pdf")]
print(f"\nPDF文档:")
for d in pdf_docs:
    print(f"- {d.file_name}: {d.status}, {d.metadata.total_pages}页")
