from langchain_community.document_loaders import PyPDFLoader


class DocumentLoader:
    """
    Responsible ONLY for loading raw documents.
    Does not parse or chunk.
    """

    @staticmethod
    def load_pdf(file_path: str):
        loader = PyPDFLoader(file_path)
        return loader.load()
