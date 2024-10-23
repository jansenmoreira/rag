## Preparando ambiente de desenvolvimento

Crie e ative um virtual environment do python e baixe as dependencias

```
python -m venv .venv
source .venv/bin/activate
pip install -U -r requirements.txt
```

Faça login no HuggingFace utlizando o `huggingface-cli`. Vai ser necessário gerar um access token com permissão de leitura utlizando o seguinte link:

```
https://huggingface.co/settings/tokens/new?tokenType=read
```

Com o token gerado utlize o seguinte comando para autenticar a linha de comando:

```
huggingface-cli login       # ou make huggingface/login
```

Execute `make dev/up` para subir as aplicações utilizando `docker compose`. Se preferir, execute o docker compose diretamente utilizando o comando:

```
docker compose -p rag up
```

Subirá uma instancia do `opensearch` e do `opensearch-dashboard` com o usuário `admin` e a senha de desenvolvimento `#Admin1234`.

Após o `opensearch` totalmente inicializado, execute os seguintes comandos para carregar o modelo de embeddings, criar pipelines e o índice que será utilizado. O script `opensearch-manager.py` possui opções de configuração que podem ser consultadas utilizando a opção `-h`.

```
python opensearch-manager.py        # ou make opensearch/setup
```

*Um exemplo de execução completa do script:*

```
INFO: Setting cluster configuration
INFO: Deleting existing models
INFO: Deploying model 'huggingface/sentence-transformers/all-mpnet-base-v2' version '1.0.1'
INFO: Waiting task XPRgupIBp_MszRlbqItG state to be COMPLETED
INFO: Task XPRgupIBp_MszRlbqItG state is CREATED, waiting 1 second...
...
INFO: Task XPRgupIBp_MszRlbqItG state is CREATED, waiting 1 second...
INFO: Task XPRgupIBp_MszRlbqItG succeeded!
INFO: Model id is XfRgupIBp_MszRlbrovH
INFO: Deleting index 'sentences'
INFO: Recreating search pipeline 'sentences_pipeline' using model 'XfRgupIBp_MszRlbrovH'
INFO: Recreating ingest pipeline 'sentences_pipeline' using model 'XfRgupIBp_MszRlbrovH'
INFO: Creating index 'sentences'
```

Pode ser verificado se o modelo está carregado consultando o dashboard disponível em (pode demorar cerca de 1 minuto):

```
http://localhost:5601/app/ml-commons-dashboards/overview
```

## Criando Knowledge Base

Abra a documentação Swagger da Indexer API disponível no endereço

```
http://localhost:8002/docs
```

Utilizando o input disponível em `input/document.json` envie o documento para o OpenSearch fazendo uma request no endpoint.

```
POST /index/
```

Os seguintes parâmetros estão disponíveis:

| Parâmetro     | Descrição |
|---------------|---|
| add_headers   | Se habilitado, adiciona os headers HTML em cada sentença |
| chunks        | Se habilitado, quebra as seções em fragmentos menores |
| chunk_size    | Controla o tamanho de cada fragmento |
| chunk_overlap | Controla o tamanho da sobreposição entre cada fragmento |

Caso precise resetar a database. Use o endpoint:

```
DELETE /index/
```

## Utilizando o Gerador de Respostas

Abra a documentação Swagger da Indexer API disponível no endereço

```
http://localhost:8001/docs
```

A geração de texto pode ser testada utilizando o endpoint. Único parâmetro obrigatório é o `prompt`.

```
POST http://localhost:8001/

{
    "prompt": "o que é o hotmart club"
}
```

Por padrão será utilizado o modelo `mistralai/Mistral-7B-Instruct-v0.3`, porém qualquer modelo `Warm` disponível no HuggingFace pode ser utlizado (alguns somente estão disponíveis após pedido ou aceitação de termos, ou mesmo apenas com subscription PRO).

Modelos `Warm` podem ser consultados aqui

```
https://huggingface.co/models?inference=warm&pipeline_tag=text-generation
```

Modelos testados:

```
https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3
https://huggingface.co/google/gemma-7b
https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct
```

Os seguintes parâmetros estão disponíveis:

| Parâmetro      | Descrição |
|----------------|---|
| prompt         | Texto fornecido pelo usuário |
| sentences_used | Número de sentenças do Knowledge Base utilizados no prompt |
| max_tokens     | Número máximo de tokens gerados |
| temperature    | Temperatura ou "criatividade" da geração de texto |
| model          | Modelo do HuggingFace utilizado na geração de texto |

Exemplos de inputs estão disponíveis na pasta `input`:

```
input/prompt1.json
input/prompt2.json
input/prompt3.json
input/prompt4.json
input/prompt5.json
```
