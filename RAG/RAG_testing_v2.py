#!/usr/bin/env python3
"""
Local RAG (Retrieval-Augmented Generation) System

This script implements a streamlined RAG system that uses local LLMs and document stores.
Following best practices for retrieval-augmented generation to enhance response quality
while mitigating hallucinations.

Features:
- In-memory indexing of documents at startup
- Automatic cleanup when the script finishes
- Support for both text and PDF documents
- Efficient vector search with FAISS
- Direct LLM integration with LlamaCpp
- Support for Llama-3.2 family models (optimized for the 1B and 3B variants)
- Domain-agnostic design suitable for any research topic
- Enhanced output quality and consistency

Usage:
  python local_rag.py --documents ./your_docs --llm ./your_model.gguf
"""

import os
import glob
import logging
import argparse
import re
import tempfile
import atexit
import shutil
from typing import List, Dict, Any, Optional

# Setup logging with reduced verbosity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("local-rag")
# Reduce logging verbosity
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("faiss").setLevel(logging.WARNING)

# Try to import LangChain components
try:
    # Import from correct packages to avoid deprecation warnings
    from langchain_community.document_loaders import TextLoader, PyPDFLoader, DirectoryLoader
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        logger.error("langchain_huggingface not installed. Please run:")
        logger.error("pip install langchain-huggingface")
        exit(1)

    from langchain_community.vectorstores import FAISS
    from langchain_community.llms import LlamaCpp

    from langchain_core.prompts import PromptTemplate
    from langchain_core.runnables import RunnablePassthrough
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.messages import AIMessage, HumanMessage

except ImportError as e:
    logger.error(f"Required packages not installed. Error: {e}")
    logger.error("Please run:")
    logger.error(
        "pip install langchain langchain-community langchain-huggingface faiss-cpu pypdf sentence-transformers llama-cpp-python")
    exit(1)


class RAGSystem:
    """
    A local RAG system that indexes documents in memory and performs
    retrieval and generation using local models, without persistent storage of the index.
    Implements best practices for retrieval-augmented generation with support for Llama-3.2 models.
    """

    def __init__(
            self,
            documents_dir: str = "./documents",
            llm_model_path: str = "./models/Llama-3.2-3B-Instruct-Q5_K_M.gguf",
            embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
            chunk_size: int = 512,  # Smaller chunk size for more precise retrieval
            chunk_overlap: int = 50,
            top_k: int = 5,
            verbose: bool = False
    ):
        """
        Initialize the RAG system.

        Args:
            documents_dir: Directory containing documents to index
            llm_model_path: Path to the LLM model file (.gguf)
            embedding_model_name: Name or path of the embedding model
            chunk_size: Size of text chunks for indexing
            chunk_overlap: Overlap between text chunks
            top_k: Number of documents to retrieve per query
            verbose: Whether to enable verbose logging
        """
        self.documents_dir = documents_dir
        self.llm_model_path = llm_model_path
        self.embedding_model_name = embedding_model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.verbose = verbose

        # Create a temporary directory for any necessary files
        self.temp_dir = tempfile.mkdtemp(prefix="rag_")
        # Register cleanup function to remove temporary directory at exit
        atexit.register(self._cleanup)

        # Store chat history
        self.chat_history = []

        # Validate model paths
        self._validate_models()

        # Determine model type based on filename
        self.model_type = self._detect_model_type()
        if self.verbose:
            logger.info(f"Detected model type: {self.model_type}")

        # Initialize embeddings
        self.embeddings = self._initialize_embeddings()

        # Load and index documents
        logger.info("Indexing documents...")
        self.vectorstore = self._create_vectorstore()
        if self.verbose:
            logger.info(f"Indexed {len(self._load_documents())} documents into {self.vectorstore._index.ntotal} chunks")
        else:
            document_count = len(self._load_documents())
            logger.info(f"Indexed {document_count} documents successfully")

        # Initialize LLM
        self.llm = self._initialize_llm()

    def _cleanup(self):
        """Remove temporary directory and files when the object is destroyed."""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            if self.verbose:
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")

    def _validate_models(self):
        """Validate that the required model files exist."""
        # Check LLM model
        if not os.path.exists(self.llm_model_path):
            raise FileNotFoundError(f"LLM model not found at {self.llm_model_path}")

    def _detect_model_type(self):
        """
        Determine the type of LLM based on the filename.

        Returns:
            String indicating the model type ('llama2', 'llama3', 'llama32', or 'other')
        """
        model_name = os.path.basename(self.llm_model_path).lower()

        if "llama-3.2" in model_name or "llama3.2" in model_name or "llama32" in model_name:
            return "llama32"
        elif "llama-3" in model_name or "llama3" in model_name:
            return "llama3"
        elif "llama-2" in model_name or "llama2" in model_name:
            return "llama2"
        else:
            return "other"

    def _initialize_embeddings(self):
        """Initialize the embedding model."""
        return HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={'device': 'cpu'}
        )

    def _initialize_llm(self):
        """Initialize the local language model with parameters optimized for the specific model type."""
        logger.info(f"Loading language model from {self.llm_model_path}")

        # Common parameters for all models
        params = {
            "model_path": self.llm_model_path,
            "temperature": 0.1,  # Lower temperature for factual responses
            "max_tokens": 1024,
            "verbose": self.verbose,
        }

        # Add model-specific parameters based on detected model type
        if self.model_type == "llama32":
            # Llama-3.2 specific settings
            params.update({
                "n_ctx": 32768,  # According to model card, context window is 8k for quantized models
                "n_batch": 512,  # Batch size for inference
                "f16_kv": True,  # Use half precision for key/value cache
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "model_kwargs": {
                    "chat_format": "llama-3.2"  # Specific format for Llama-3.2
                }
            })
        elif self.model_type == "llama3":
            # Llama-3 specific settings
            params.update({
                "n_ctx": 8192,
                "n_batch": 512,
                "f16_kv": True,
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "model_kwargs": {
                    "chat_format": "llama-3"
                }
            })
        else:
            # Default parameters for other models (including Llama-2)
            params.update({
                "n_ctx": 4096,
                "n_batch": 512,
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
            })

        return LlamaCpp(**params)

    def _load_documents(self) -> List:
        """Load documents from the documents directory."""
        if self.verbose:
            logger.info(f"Loading documents from {self.documents_dir}")

        loaders = []

        # Text files
        if glob.glob(os.path.join(self.documents_dir, "**/*.txt"), recursive=True):
            text_loader = DirectoryLoader(
                self.documents_dir,
                glob="**/*.txt",
                loader_cls=TextLoader,
                show_progress=self.verbose
            )
            loaders.append(text_loader)

        # PDF files
        if glob.glob(os.path.join(self.documents_dir, "**/*.pdf"), recursive=True):
            pdf_loader = DirectoryLoader(
                self.documents_dir,
                glob="**/*.pdf",
                loader_cls=PyPDFLoader,
                show_progress=self.verbose
            )
            loaders.append(pdf_loader)

        # Load all documents
        documents = []
        for loader in loaders:
            documents.extend(loader.load())

        if self.verbose:
            logger.info(f"Loaded {len(documents)} documents")
        return documents

    def _create_vectorstore(self):
        """Create a vector store from documents with sliding window chunking for better retrieval."""
        # Load documents
        documents = self._load_documents()

        if not documents:
            logger.warning("No documents found to index.")
            # Create an empty vector store if no documents found
            empty_texts = ["No documents are available in the corpus."]
            return FAISS.from_texts(empty_texts, self.embeddings)

        # Process and index documents
        if self.verbose:
            logger.info("Processing and indexing documents...")

        # Use sliding window approach as recommended in best practices
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        # Split documents into chunks
        chunks = text_splitter.split_documents(documents)
        if self.verbose:
            logger.info(f"Created {len(chunks)} document chunks")

        # Create vector store from chunks
        return FAISS.from_documents(chunks, self.embeddings)

    def _format_context(self, source_documents):
        """
        Format retrieved documents into a consistent context string.

        Args:
            source_documents: List of documents retrieved from the vector store

        Returns:
            Formatted context string
        """
        context = ""
        for i, doc in enumerate(source_documents):
            source = doc.metadata.get("source", "unknown source")
            source = os.path.basename(source) if "/" in source else source
            page = doc.metadata.get("page", "")
            page_info = f" (page {page})" if page else ""

            context += f"[Source {i + 1}: {source}{page_info}]\n"
            context += f"{doc.page_content.strip()}\n\n"

        # Determine appropriate context length based on model
        max_context_length = 15000 if self.model_type in ["llama3", "llama32"] else 12000

        # Truncate if needed
        if len(context) > max_context_length:
            context = context[:max_context_length] + "...[truncated]"

        return context

    def query(self, question: str) -> Dict[str, Any]:
        """
        Query the RAG system with a question.

        Args:
            question: The question to answer

        Returns:
            Dictionary containing the answer and source documents
        """
        try:
            # Get source documents using retrieval
            retriever = self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": self.top_k}
            )
            source_documents = retriever.invoke(question)

            if self.verbose:
                logger.info(f"Retrieved {len(source_documents)} documents for query: {question}")
                for i, doc in enumerate(source_documents):
                    logger.info(f"Document {i + 1}: {os.path.basename(doc.metadata.get('source', 'unknown'))}")

            # Format context from documents
            context = self._format_context(source_documents)

            # Use appropriate prompt format based on model type
            if self.model_type == "llama32":
                # Llama-3.2 specific chat format
                prompt = f"""<|system|>
You are a helpful and concise assistant that answers questions based only on the provided information.
<|user|>
I need information about the following:
{question}

Here is the relevant information:
{context}

Please provide a comprehensive and accurate answer based only on this information.
<|assistant|>
"""
            elif self.model_type == "llama3":
                # Llama-3 specific chat format
                prompt = f"""<|start_header_id|>system<|end_header_id|>
You are a research assistant providing information based on the documents available to you.

<|start_header_id|>user<|end_header_id|>
I need information about the following question:
{question}

Here is relevant information from documents:
{context}

Please provide a comprehensive answer based only on this information. If the information to answer the question is not available in the documents, clearly state this.

<|start_header_id|>assistant<|end_header_id|>
"""
            else:
                # Standard prompt for other models (including Llama-2)
                prompt = f"""You are a research assistant providing information based on the documents available to you.

QUESTION: {question}

RETRIEVED INFORMATION:
{context}

INSTRUCTIONS (DO NOT INCLUDE THESE IN YOUR RESPONSE):
1. Answer ONLY based on the information in the retrieved documents. Do not use external knowledge.
2. If the documents don't contain relevant information to answer the question fully, clearly state what information is missing.
3. If the question appears nonsensical or cannot be answered based on the documents, politely explain why.
4. Start with a direct answer to the question, then provide supporting details.
5. Organize information logically, using numbered lists where appropriate.
6. Be concise but complete.
7. Use simple formatting only.
8. Never make up information that's not in the documents.
9. If multiple documents contain relevant information, synthesize it into a coherent answer.
10. Do not repeat phrases like "According to the documents" in every sentence.

ANSWER:"""

            # Directly invoke the LLM
            raw_answer = self.llm.invoke(prompt)

            # Clean up the answer with improved processing
            answer = self._clean_llm_response(raw_answer)

            # Update chat history
            self.chat_history.append(HumanMessage(content=question))
            self.chat_history.append(AIMessage(content=answer))

            # Format sources for display
            sources = []
            for doc in source_documents:
                source = {
                    "source": doc.metadata.get("source", "unknown"),
                    "page": doc.metadata.get("page", None)
                }
                sources.append(source)

            return {
                "answer": answer,
                "sources": sources
            }
        except Exception as e:
            logger.error(f"Error querying RAG system: {str(e)}")
            if self.verbose:
                import traceback
                logger.error(traceback.format_exc())
            return {
                "answer": f"I encountered an error while processing your question. Please try again or rephrase your query.",
                "sources": []
            }

    def _clean_llm_response(self, response: str) -> str:
        """
        Clean the LLM response by removing unwanted patterns and formatting artifacts.

        Args:
            response: The raw LLM response

        Returns:
            Cleaned response string
        """
        if not response:
            return "I could not generate an answer based on the available documents."

        # Model-specific cleaning
        if self.model_type == "llama32":
            # Remove Llama-3.2 specific tokens
            response = re.sub(r'<\|system\|>.*?<\|user\|>', '', response, flags=re.DOTALL)
            response = re.sub(r'<\|user\|>.*?<\|assistant\|>', '', response, flags=re.DOTALL)
            response = re.sub(r'<\|assistant\|>', '', response)
        elif self.model_type == "llama3":
            # Remove Llama-3 specific tokens
            response = re.sub(r'<\|start_header_id\|>.*?<\|end_header_id\|>', '', response, flags=re.DOTALL)

        # Remove any leading/trailing whitespace
        cleaned = response.strip()

        # Check if the response is just whitespace or very short
        if not cleaned or len(cleaned) < 10:
            return "I could not generate a meaningful answer based on the available documents."

        # Remove any system-level instructions or metadata that leaked into the response
        patterns_to_remove = [
            r"INSTRUCTIONS.*?ANSWER:",
            r"INSTRUCTIONS \(DO NOT INCLUDE THESE IN YOUR RESPONSE\):.*?ANSWER:",
            r"^QUESTION:.*?\n",
            r"^RETRIEVED INFORMATION:",
            r"1\. Answer ONLY based.*?10\. Do not repeat phrases.*?\n\n",
            r"ANSWER:",
            r"### Question \d+:.*?\n",
            r"### Answer \d+:.*?\n",
            r"Please provide a comprehensive.*?information\.",
            r"I need information about the following.*?\n",
            r"Here is (?:the )?relevant information.*?:\n"
        ]

        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Remove lines that are obviously part of the prompt structure
        lines = cleaned.split('\n')
        filtered_lines = []
        skip_line = False

        for line in lines:
            # Skip lines that are clearly part of document headers
            if re.match(r'^\s*\[Source \d+:', line, re.IGNORECASE):
                skip_line = True
                continue

            # Skip formatting artifacts from the model
            if re.match(r'^\s*(\\section|\\begin\{|\\end\{|\\item|\\strong)', line, re.IGNORECASE):
                continue

            # If we've been skipping and found a blank line, stop skipping
            if skip_line and not line.strip():
                skip_line = False
                continue

            if not skip_line:
                filtered_lines.append(line)

        cleaned = '\n'.join(filtered_lines)

        # Remove LaTeX, HTML and markdown artifacts
        cleaned = re.sub(r'\\section\{[^}]+\}', '', cleaned)
        cleaned = re.sub(r'\\begin\{[^}]+\}', '', cleaned)
        cleaned = re.sub(r'\\end\{[^}]+\}', '', cleaned)
        cleaned = re.sub(r'\\item', '', cleaned)
        cleaned = re.sub(r'\\strong\{([^}]+)\}', r'\1', cleaned)
        cleaned = re.sub(r'\\emph\{([^}]+)\}', r'\1', cleaned)
        cleaned = re.sub(r'\\textbf\{([^}]+)\}', r'\1', cleaned)
        cleaned = re.sub(r'\\textit\{([^}]+)\}', r'\1', cleaned)
        cleaned = re.sub(r'<[^>]+>', '', cleaned)  # Remove HTML tags

        # Remove repetitive patterns
        cleaned = re.sub(r'(The .+?\n)\1+', r'\1', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'(are listed as follows:\s*\n\s*\n)\1+', r'\1', cleaned, flags=re.DOTALL)

        # Final cleanup of any double spaces or multiple newlines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r"  +", " ", cleaned)
        cleaned = cleaned.strip()

        # If we've stripped too much, provide a fallback
        if not cleaned or len(cleaned) < 10:
            return "Based on the documents, I could not synthesize a complete answer to your question."

        return cleaned

    def run_interactive(self):
        """Run the RAG system in interactive mode."""
        model_desc = "Llama-3.2" if self.model_type == "llama32" else \
            "Llama-3" if self.model_type == "llama3" else \
                "Llama-2" if self.model_type == "llama2" else \
                    "Unknown model type"

        print(f"\n===== Local RAG Chat System ({model_desc}) =====")
        print(f"Documents directory: {self.documents_dir}")
        print(f"LLM: {os.path.basename(self.llm_model_path)}")
        print("Type 'exit' to quit, 'reindex' to reindex documents")
        print("====================================\n")

        while True:
            user_input = input("\nYou: ").strip()

            if user_input.lower() == "exit":
                print("Exiting. Goodbye!")
                break
            elif user_input.lower() == "reindex":
                print("Reindexing documents...")
                self.vectorstore = self._create_vectorstore()
                print("Reindexing complete.")
                continue
            elif not user_input:
                continue

            print("\nThinking...")
            result = self.query(user_input)

            print(f"\nAssistant: {result['answer']}")

            if result['sources']:
                print("\nSources:")
                # Deduplicate sources
                unique_sources = []
                unique_source_texts = set()

                for source in result['sources']:
                    source_text = source['source']
                    if source.get('page') is not None:
                        source_text += f" (page {source['page']})"

                    if source_text not in unique_source_texts:
                        unique_sources.append(source)
                        unique_source_texts.add(source_text)

                # Print deduplicated sources
                for i, source in enumerate(unique_sources, 1):
                    source_text = source['source']
                    if source.get('page') is not None:
                        source_text += f" (page {source['page']})"
                    print(f"{i}. {source_text}")


def main():
    """Main function to run the local RAG system."""
    parser = argparse.ArgumentParser(description="Local RAG Chat System")
    parser.add_argument("--documents", default="./documents",
                        help="Directory containing documents (default: ./documents)")
    parser.add_argument("--llm", default="./models/Llama-3.2-3B-Instruct-Q5_K_M.gguf",
                        help="Path to local LLM model file (.gguf) (default: ./models/Llama-3.2-3B-Instruct-Q5_K_M.gguf)")
    parser.add_argument("--embeddings", default="sentence-transformers/all-MiniLM-L6-v2",
                        help="Name of embedding model to use")
    parser.add_argument("--chunk-size", type=int, default=512,
                        help="Size of document chunks for indexing")
    parser.add_argument("--chunk-overlap", type=int, default=50,
                        help="Overlap between document chunks")
    parser.add_argument("--top-k", type=int, default=15,
                        help="Number of chunks to retrieve per query")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    try:
        # Check if documents directory exists
        if not os.path.isdir(args.documents):
            logger.error(f"Documents directory not found: {args.documents}")
            print(f"\nError: Documents directory not found: {args.documents}")
            print(f"Please create this directory or specify a different one with --documents")
            return

        # Check if LLM model exists
        if not os.path.isfile(args.llm):
            logger.error(f"LLM model file not found: {args.llm}")
            print(f"\nError: LLM model file not found: {args.llm}")
            print(f"Please download an appropriate LLM model or specify the correct path with --llm")
            return

        # Initialize the RAG system
        rag_system = RAGSystem(
            documents_dir=args.documents,
            llm_model_path=args.llm,
            embedding_model_name=args.embeddings,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            top_k=args.top_k,
            verbose=args.verbose
        )

        # Run the interactive chat
        rag_system.run_interactive()

    except FileNotFoundError as e:
        logger.error(f"Error: {str(e)}")
        print(f"\nError: {str(e)}")
        print("Please check that all required files and directories exist.")

    except Exception as e:
        logger.error(f"Error running RAG system: {str(e)}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        print("\nAn error occurred. Check the logs for details.")
        print("Please make sure all dependencies are installed:")
        print(
            "pip install langchain langchain-community langchain-huggingface faiss-cpu pypdf sentence-transformers llama-cpp-python")


if __name__ == "__main__":
    main()