# RagTalk

### RagTalk MVP Architecture - Logical System Design

```
       ┌─────────────────────────────────────────────────────────────┐
       │                        CLIENT (UI)                          │
       │  - PDF Upload            - Streaming Chat Response          │
       │  - Processing Status     - Multiple Document Selection      │
       └──────────────┬───────────────────────────────▲──────────────┘
                      │                               │
            1. POST /upload/                  10. WebSocket / Webhook
            11. POST /chat/                   (Status & LLM Stream)
                      │                               │
      ┌───────────────▼───────────────────────────────┴──────────────┐
      │                  DJANGO WEB SERVER (DAPHNE)                  │
      │  - Validation       - Auth (Stubbed)     - WebSocket Router  │
      │  - File Persistence - State Management   - Async Handlers    │
      └───────────────┬───────────────────────────────┬──────────────┘
                      │                               │
            2. Save Record                    4. Trigger Task
            3. Write File                     (asyncio.create_task)
                      │                               │
      ┌───────────────▼───────────┐       ┌───────────▼──────────────┐
      │     RELATIONAL STORE      │       │ DOCUMENT INGESTION SVC   │
      │     (SQLite/Postgres)     │       │                          │
      │  - Metadata (Hash/Size)   │       │ 5. Load (PyPDF)          │
      │  - Status Tracking        │       │ 6. Chunk (Recursive)     │
      │  - File Paths             │       │ 7. Embed (OpenAI)        │
      └───────────────┬───────────┘       └───────────┬──────────────┘
                      │                               │
             ┌────────▼──────────┐           ┌────────▼──────────────┐
             │   FILE STORAGE    │           │     VECTOR STORE      │
             │   (Local Disk)    │           │  (ChromaDB In-Memory) │
             └───────────────────┘           │  - Semantic Indexing  │
                                             └────────▲──────────────┘
                                                      │
      ┌───────────────────────────────────────────────┴──────────────┐
      │                 LANGGRAPH RAG ORCHESTRATOR                   │
      │                                                              │
      │  - PII Redactor (Regex Guardrails)                           │
      │  - Retriever (k=4)                                           │
      │  - Prompt Augmentation (Few-Shot / CoT)                      │
      │  - LLM Generation (GPT-4o-mini)                              │
      └──────────────────────────────────────────────────────────────┘

```


### Document Ingestion Flow

```
User uploads PDF
        │
        ▼
upload_document (Django View)
        │
        ▼
Compute file_hash
        │
        ├── If exists → return existing doc (200)
        │
        └── Else:
              │
              ▼
        Save Document model
              │
              ▼
        Background ingestion task
              │
              ▼
        1. Load PDF
        2. Chunk text
        3. Generate embeddings
        4. Store in Vector DB

```
-------------------------------------------------------------------------------------------

### Overview

Enterprises, governments and nearly all organization have their fair share of information locked up in PDF.
This MVP app is solving this problem by using asynchronous RAG architecture optimized for extensibility and easy migration from MVP to production because the architecture and design takes into account cost-awareness that can come from uncontrolled LLM calls. Additionaly, by incorporating memory for the chatbot which can be easily externalized using tools like distributed redis,  adding asynchronous communication, containerization which planned but shelved for the future, it is beginning to set the foundations for horizontal scalability and the opportunity for the production system to meet latency targets. This MVP handles everything from asynchronous file upload through file indexing using orchestration in the background that allows for concurrent users to document chat through asynchronous communication. Specifically, it uses webhook to stream llm response during chat and to track states during file upload.
The app also uses webhook for notifying the user via the UI if the document has uploaded successfully or not and whether it has been indexed or not.

Design principles (extensibility, failure isolation, observability-fitst)

-------------------------------------------------------------------------------------------
###	Quick setup instructions

I thought of creating a docker-compose file instead of the many commands you need to run below, but decided against it to reduce reviewer friction. However, pinned versions of python packages were in requirements.txt to ensure no dependency pain when running this app.

- Clone the repo to your local machine and make sure you have Python running. I used Python 3.11
- Create a python virtual environment in the parent folder containing the cloned repo by running

```
python3 -m venv env-3.11
```

then run activate it with still why you are still in the parent folder of the cloned repo

```
source env-3.11/bin/activate
```

#### Next change directory(cd) into the cloned repo and installing the python packages you will need by running
```
pip3 install -r requirements.txt
```

Do a quick check that the Django server can start by running
```
python3 manage.py runserver
```

Run the tests in the echo app

####    Generate the migration file for the Document model, the django app here is called echo
```
python manage.py makemigrations echo
```

#### Apply migrations to db
```
python manage.py migrate echo

python manage.py test echo
```

#### run the text in specific file
```
python manage.py test echo.tests.test_rag_quality 

```

-------------------------------------------------------------------------------------
#### Access the UI to upload documents for chat

You would need to have ran the migrations to setup and create tables  before you can start the server.
See the previous step or see above. 

Start the Django server with:

```
 python3 manage.py runserver

```
Visit the url 

```
http://127.0.0.1:8000/echo/
```

Upload any PDF, select the radio button where you have more than one file upload and start chatting away.
Note the selected pdf will be highlighted.

-----------------------------------------------------------------------------------------------
#### Memory

The app uses InMemory store to manage memory though this is not persisted or long lived but it demonstrates
that it can easily swap that out for PineCone. Redis or your preferred vector store.

------------------------------------------------------------------------

####  Architecture overview (a simple diagram is great but not required)

The overall architecture is to allow for easy extensibility , maintainance and scalability.

Hence, I implemented interfaces where applicable for instance the VectorStore abstraction layer, allowing the ingestion pipeline to remain agnostic of the underlying provider (Chroma vs. Pinecone).
We design for horizontally scalability to allow for parallel processing in future.
The architecture prioritizes uses experience hence the incorporation of websocket for realtime experience.

The MVP architecture allows for Idempotency when loading files and allows easy visibility into
State transitions (document lifecycle: uploaded → indexed → queryable)

----------------------------------------------------------------------
Table showing some architectural choices
--------------------------------------------------------------------------------------------------
Layer	   Responsibility	                  Logic
--------------------------------------------------------------------------------------------------
View	     Gatekeeper	                    Calculates Hash + Checks Existence + Returns 200 or 202.
---------------------------------------------------------------------------------------------------
Model	     Track & manage state	        unique=True on file_hash prevents any race-condition duplicates.
-------------------------------------------------------------------------------------------------------
Task	     Orchestrator	                       ingest_document_background (in tasks.py) bridges Sync/Async.
------------------------------------------------------------------------------------------------------
Tests	     Validation	                             TransactionTestCase + patch to verify call_count.
-----------------------------------------------------------------------------------------------------
VectorStore  interface over vector stores            Easily swap different vector stores
------------------------------------------------------------------------------------------------------
rag_engine   manages langgraph orchestration          Easy to extend langgarph workflow
-----------------------------------------------------------------------------------------------------
DocumentIngestionService  deduplication, chunking    Avoid context poisoning and inefficient query
---------------------------------------------------------------------------------------------------
websocket                  Realtime                  Good for user experience
--------------------------------------------------------------------------------------------------

### What would be required to productionize your solution, make it scalable and deploy it on a hyper-scaler such as AWS / GCP / Azure?

-----------------------------------------------------------------------------------------------
          What would be required to productionize your solution

First for the MVP I tried to keep the setup as simple as possible, so the reviewer will not need to install
too many things in order to run the app. So we will need to:
   - Use a proper asynchronous job queue instead of Python's asyncio create_task which i used to show the possibility. This will for more concurrent users to be served. This will need document and processing and indexing. Good caching wil also help with failed document processing and by extension using experience
    because it ensure no user upload is 'lost' in the system.
   - There will be a need to introduce different caching approaches. For instance maximize key-value 
   caching to speed up inference and introduce response caching like semantic cache to speed up response to questions that are semanticaly similar and have been answered recently.
   - High performance database that will not break under high usage.
   - Add authentication, authorization and better security hardening.
   - Add observability, I was going to add langsmith for tracing but left it to keep the app runnable 
     without the need to comment out section of the code incase you dont use that tool.
   - The app will require more robust grounding and eval. This has  some test that does some eval where it judges faithfulness that is if the answer derived ONLY from the context provided and relevance, does the answer actually address the user's question?
   - It will need to expand into a multi-document indexer instead of just PDF as it currently stands.
   - We will need rateliming and cost control. This made more so because recursive LLM calls can lead to profit wipeout. This necessitates the implementation of rate limiting per user, and track token spend.
   - Security especially of data and keys. for this MVP I have kept Environment Variables (.env) for API keys 
     in .bashrc but for production we would want to consider cloud providers like Azure keyvault, Terraform vault and aws secrets manager as they make it easier to pass SOC , GDPR compliance
   - To productionize we will need more circuit breakers for LLM APIs, the MVP has the stripped down version using Python's tenacity package to handle timeout error and based on that trigger the switch of llms
   - Implement Backpressure handling, so the system is not overwhelmed.
b. Make it scalable and deploy it on a hyper-scaler such as AWS / GCP / Azure
  Infrastructure needs
    You can scale deployment by using containerization and  Infrastruture as code with tools like kubernetes, Ansible and terraform for deploying the app with all its moving part.

    Depending on the business goals, you will need to use local models alongside api's from Openai, Anthropic, Google. The use of local llm will necessitate having GPU clusters 

    You will need to able to scale horizontally and implement autoscaing policies alongside Blue/green or 
    Multi-region deployment strategy

  Load balancers
    These will be needed to handle and distribute traffic across servers as you scale horizontally.

------------------------------------------------------------------------------------------------

### RAG/LLM approach & decisions: Choices considered and final choice for LLM / embedding model / vector database / orchestration framework, prompt & context management, guardrails, quality, observability

         RAG/LLM approach & decisions

For the MVP the RAG  approach used focused on simplicity by using RecursiveCharacterTextSplitter.
Here we trade off simplicity for less quality result the bigger the document. Things that
out to be closer because they semantically the same in returned in same query will end up being missed at times leading to poor retrieval by extension giving insufficient context to the llm and the attendant poor llm response or answer.
Though overlaps are often added, most time it is not sufficient mitigation against the retrieval issues 
I considered semantic chunking but felt it was an overkill.

Another thing worthy of note is hybrid sarch combining BM25 keyword search with Vector Search (Reranking) to improve retrieval of specific terminology within documents.

Ultimately for the MVP i was primarily trying to balance "RAG Triad" (Context Relevance, Groundedness, Answer Relevance).

------------------------------------------------------------------------------------------------------
             VectoreStore 

I have exprience with both ElasticSearch and Redis but did not go with elasticstore because it will be a mismatch for the amount of data the mvp will use. As for redis it is quick and easy to setup with docker
but ultimately did not pick because I wanted to give the reviewer less things to install. More importantly,
I think vector store like Chromadb and Faiss are still quicker to set and a better fit if like me 
you will be using Inmemory store for state management.

--------------------------------------------------------------------------------------------------------
             Embedding Model

I used openai small embedding model for speed and reduce cost. Initially, I thought I would use BGE for embedding which I already use locally, but picked Openai because more companies have tested it in production. OpenAI text-embedding-3-small excellent price-to-performance ratio ultimately means that it offers better convenience than self-hosted BGE models for this MVP and scale with you.

--------------------------------------------------------------------------------------------------

              Prompt & context management 

For prompt, there are quite a few things to worry about from prompt injection, to sensitive PII information,
then there is profane and not safe for work words from either the user or llm response.
I thought of using Micorosft Presido for PII but that has Spacy as a dependency, so I just used
Python's re and limited it to just checking for email and phone number to demonstrate that i know that it is something I need address. The pii_redactor function is called on user submitted prompt and on llm response.
 
To make the prompt more effective I decided to combine few shot examples and chain of though reasoning in addition to rewriting use questions or expanding it. Initially, Initially I wanted only to expand the questions but it did not give me the high quality result.
Context management for this MVP was mainly about evaluating how much results to fetch and pass to the llm.
Even though this data is small I was mindfull of the fact that larger size context does not mean better result
and was equally weary of context poisoning so I settled on the search having a limit of 4. It is small but good
enough for an mvp.  

---------------------------------------------------------------------------------------------------

            Orchestration framework, guardrails, quality, observability

I used Langchain and Langgraph because they enables deterministic orchestration. Langchain has LCEL and Langgraph has the graph workflow for building agents. I used CrewAI briefly in the past but it did not have some these deterministic orchestration at that time. Another reason for picking  Langchain / Langgraph is their ecosystem because of community, documentation, widespread adoption and better tooling.
Using Langgraph allowed to add guard rails like filtering for PII at the beginning of the orchestration
on user input and at the end after LLM response. This also doubles as quality check and beyond
the mvp there is much more we can do between Langgraph nodes.

 There are production-grade tools that enable safety like NeMo Guardrails or Guardrails AI.
 For this MVP as a way to observe quaity, I Implemented a test_rag_quality suite using LLM-as-a-judge to establish a baseline. This allows us to quantify if a change in the prompt or chunking strategy actually improves the system.

-----------------------------------------------------------------------------------------------------

###  Engineering standards you’ve followed (and maybe some that you skipped)
I have used systems design to ensure the mvp integrate seamlessly.
I have tried to use single responsible principle, splitting the classes and app with this in mind.
For performance and scalability I designed the app to both be async and parallel processing so it easy to offload work things to background jobs in such away that it is easy to swap out and use more appropriate tools when it is time to move off MVP for more scaleable option.
Resilience was considered hence you will see that for llm calls for instance it does not only handle 
timeout error it has a fallback in place to automatically call another LLM, while for the MVP only
two llm were involved this can easily be widened in a production scenario. 
The document chat has memory to improve user experience and be fit for real world use-cases

Another engineering principle used in this MVP is testing philosophy , stable api contracts and the app
has clean architecture boundaries.

----------------------------------------------------------------------------------------------------

####   How you used AI tools in your development process 

I used AI to for brainstorming and evaluations. I used it to evaluate different approaches and their trade-offs.
I equally use it for quick implementation to spike out different approaches, runand evaluate them results before knowing what to settle. I prefer to give the same scenario to different AI tools, compare their response, give them my feedback and evaluation and guard them when I think their response is missing the mark.
I also give the response of one AI to another asking them to critique.

------------------------------------------------------------------------------------------------------

####  What you'd do differently with more time 
 - For document chunking I would have used semantic chunking which allows for much larger documents to be indexed and better results.
 - I will use multi query where I will break the queries into sub query and use that to improve the answer.
 - I will use Redis instead of ChromaDb because it allows for both keyword and similarity search, as I prefer to combine both and then do reranking using Okapi BM25 for ranking. Redis utility also means we can use it for some sort of graph database without adding a new infrastrucure in Neo4j.
 - Semantic caching is another thing I will have love to do, if time permitted. Again by installing Redis
   I would have killed so many birds with this one proverbial stone ):
 - I will use Miccrosoft Presido to filter and redaact PII data, use deoxify and similar tools to filter profanity etc
 - Move the UI and frontend to be Reactjs based because it allows for us to build better interactivity into the app.

----------------------------------------------------------------------------------------------------------