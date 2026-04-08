from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

def build_retriever(pdf_path):

    loader = PyPDFLoader(pdf_path)
    docs = loader.load()

    vectordb = Chroma.from_documents(
        docs,
        OpenAIEmbeddings()
    )

    return vectordb.as_retriever()