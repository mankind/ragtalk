from langchain.text_splitter import RecursiveCharacterTextSplitter


class DocumentParser:
    """
    Responsible for chunking documents.
    Decoupled from loading source.
    """

    @staticmethod
    def chunk_documents(documents):
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=200,
        )
        return splitter.split_documents(documents)
