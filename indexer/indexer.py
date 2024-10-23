import json
import re
from typing import List

from fastapi import FastAPI
from langchain_text_splitters import (
    HTMLHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from opensearchpy import OpenSearch
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    opensearch_host: str = Field(default="localhost", alias="OPENSEARCH_HOST")
    opensearch_port: int = Field(default=9200, alias="OPENSEARCH_PORT")
    opensearch_user: str = Field(default="admin", alias="OPENSEARCH_USER")
    opensearch_password: str = Field(
        default="#Admin1234", alias="OPENSEARCH_PASSWORD"
    )
    opensearch_https: bool = Field(default=True, alias="OPENSEARCH_HTTPS")
    opensearch_verify_ssl: bool = Field(default=False, alias="OPENSEARCH_VERIFY_SSL")
    opensearch_index: str = Field(default="sentences", alias="OPENSEARCH_INDEX")


settings = Settings()

opensearch = OpenSearch(
    hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
    http_auth=(settings.opensearch_user, settings.opensearch_password),
    use_ssl=settings.opensearch_https,
    verify_certs=settings.opensearch_verify_ssl,
)

headers_to_split = [
    ("h1", "Header 1"),
    ("h2", "Header 2"),
    ("h3", "Header 3"),
    ("h4", "Header 4"),
    ("h5", "Header 5"),
    ("h6", "Header 6"),
]

app = FastAPI(title="Document Indexer API")

spaces_pattern = re.compile(r"\s+")


class IndexDocument(BaseModel):
    content: str = Field(description="HTML/Text to add to vector database")
    add_headers: bool = Field(
        default=False, description="If true, adds section headers to indexed sentences"
    )
    chunks: bool = Field(default=True, description="If true, break section into chunks")
    chunk_size: int = Field(default=300, description="Maximum size of a chunk")
    chunk_overlap: int = Field(default=50, description="How much each chunk overlaps")


@app.delete("/index/")
def delete_documents():
    response = opensearch.delete_by_query(
        index=settings.opensearch_index, body={"query": {"match_all": {}}}
    )
    
    return response


@app.post("/index/")
def index_document(request: IndexDocument) -> List[str]:

    # Usa as tags de header do HTML para quebrar texto em seções
    html_splitter = HTMLHeaderTextSplitter(headers_to_split)

    splits = html_splitter.split_text(request.content)

    # Se a opção `chunk` estiver habilitada, quebra seções em tamanhos
    # `chunk_size` controla o tamanho máximo de um fragmento
    # `chunk_overlap` controla o quanto os framentos se sobrepõem
    if request.chunks:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=request.chunk_size, chunk_overlap=request.chunk_overlap
        )

        splits = text_splitter.split_documents(splits)

    sentences = []
    documents = ""

    # Prepara sentenças adicionando o conteúdo do header se essa opção estiver habilitada
    # Cria request bulk para ser enviada ao OpenSearch
    for split in splits:
        sentence = ""

        if request.add_headers:
            sentence += " ".join(split.metadata.values())

        sentence += f" {split.page_content}"

        sentence = spaces_pattern.sub(" ", sentence)
        sentence = sentence.strip()
        sentences.append(sentence)

        documents += json.dumps(
            {"index": {"_index": settings.opensearch_index}}, separators=(",", ":")
        )
        documents += "\n"
        documents += json.dumps({"sentence": sentence}, separators=(",", ":"))
        documents += "\n"

    response = opensearch.bulk(documents, timeout=30)

    if response["errors"]:
        raise RuntimeError(response)

    return sentences
