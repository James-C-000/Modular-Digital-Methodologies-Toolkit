#!/usr/bin/env python3
"""
Optimized Qwen 3.5 RAG (Retrieval-Augmented Generation) System

This script implements a streamlined RAG system optimized for Qwen 3.5 models.
It features enhanced performance, improved robustness, and cleaner code organization
while maintaining high-quality retrieval and generation capabilities.

Features:
- Optimized specifically for Qwen 3.5 models
- Efficient in-memory document indexing
- Automatic resource cleanup
- Support for text and PDF documents
- Fast vector search with FAISS
- Optimized chunking and retrieval strategies
- Enhanced prompt engineering for Qwen 3.5
- Robust error handling and recovery
- Performance-focused parameter tuning

Usage:
  python qwen_rag.py --documents ./your_docs --llm ./your_qwen_model.gguf
"""

import os
import glob
import logging
import argparse
import re
import tempfile
import atexit
import shutil
import time
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

# Setup logging with reduced verbosity
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("qwen-rag")

# Reduce logging verbosity for dependencies
for module in ["sentence_transformers", "faiss", "transformers", "filelock", "huggingface_hub"]:
    logging.getLogger(module).setLevel(logging.WARNING)

# Try to import required components
try:
    # Import from correct packages to avoid deprecation warnings
    from langchain_community.document_loaders import (
        TextLoader, PyPDFLoader, DirectoryLoader,
        BSHTMLLoader, CSVLoader, Docx2txtLoader,
    )
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    from langchain_huggingface import HuggingFaceEmbeddings

    from langchain_community.vectorstores import FAISS
    from langchain_community.llms import LlamaCpp

    from langchain_core.documents import Document
    from langchain_core.prompts import PromptTemplate
    from langchain_core.messages import AIMessage, HumanMessage

except ImportError as e:
    logger.error(f"Required packages not installed. Error: {e}")
    logger.error("Please run:")
    logger.error(
        "pip install langchain langchain-community langchain-huggingface faiss-cpu pypdf sentence-transformers llama-cpp-python beautifulsoup4 docx2txt")
    exit(1)


# Registry mapping file extensions to their LangChain document loader.
# TextLoader handles plain-text formats (txt, md, json) directly.
# Specialised loaders handle structured/binary formats (pdf, html, csv, docx).
SUPPORTED_EXTENSIONS = {
    ".txt": TextLoader,
    ".pdf": PyPDFLoader,
    ".md": TextLoader,
    ".json": TextLoader,
    ".html": BSHTMLLoader,
    ".csv": CSVLoader,
    ".docx": Docx2txtLoader,
}


class QwenRAGSystem:
    """
    An optimized RAG system designed specifically for Qwen 3.5 models.

    This class provides a streamlined implementation that focuses on:
    1. Maximum performance with Qwen 3.5 models
    2. Efficient memory usage and processing
    3. Robust error handling and recovery
    4. Clean, maintainable code structure
    """

    def __init__(
            self,
            documents_dir: str = "./documents",
            llm_model_path: str = "./models/Qwen3.5-4B-Q4_K_M.gguf",
            embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
            chunk_size: int = 512,
            chunk_overlap: int = 64,
            top_k: int = 4,
            n_threads: int = 4,
            context_window: int = 32768,
            verbose: bool = False,
            enable_thinking: bool = False,
            n_gpu_layers: int = 0
    ):
        """
        Initialize the Qwen 3.5 RAG system.

        Args:
            documents_dir: Directory containing documents to index
            llm_model_path: Path to the Qwen 3.5 model file (.gguf)
            embedding_model_name: Name or path of the embedding model
            chunk_size: Size of text chunks for indexing
            chunk_overlap: Overlap between text chunks
            top_k: Number of documents to retrieve per query
            n_threads: Number of threads to use for parallel processing
            context_window: Context window size for the Qwen 3.5 model
            verbose: Whether to enable verbose logging
            enable_thinking: Enable chain-of-thought thinking mode
            n_gpu_layers: Number of layers to offload to GPU (-1 for all, 0 for CPU only)
        """
        self.documents_dir = os.path.abspath(documents_dir)
        self.llm_model_path = os.path.abspath(llm_model_path)
        self.embedding_model_name = embedding_model_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.n_threads = n_threads
        self.context_window = context_window
        self.verbose = verbose
        self.enable_thinking = enable_thinking
        self.n_gpu_layers = n_gpu_layers

        # Performance metrics
        self.perf_metrics = {
            "indexing_time": 0,
            "doc_count": 0,
            "chunk_count": 0,
            "queries": 0,
            "total_query_time": 0
        }

        # Create a temporary directory for processing
        self.temp_dir = tempfile.mkdtemp(prefix="qwen_rag_")
        atexit.register(self._cleanup)

        # Store chat history
        self.chat_history = []

        # Validate LLM model
        self._validate_models()

        # Initialize system components in sequence
        start_time = time.time()

        logger.info("Initializing embedding model...")
        self.embeddings = self._initialize_embeddings()

        logger.info(f"Indexing documents from {self.documents_dir}...")
        self.vectorstore = self._create_vectorstore()
        self._query_cache: Dict[str, List] = {}

        self.perf_metrics["indexing_time"] = time.time() - start_time

        logger.info(f"Loading Qwen model from {llm_model_path}...")
        self._inference_params = self._get_llm_params(self.enable_thinking)
        self.llm = self._initialize_llm()

        logger.info(f"Initialization complete ({self.perf_metrics['indexing_time']:.2f}s)")
        logger.info(
            f"Indexed {self.perf_metrics['doc_count']} documents into {self.perf_metrics['chunk_count']} chunks")

    def _cleanup(self):
        """Remove temporary directory and files when the object is destroyed."""
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            if self.verbose:
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")

    def _validate_models(self):
        """Validate that the required model files exist."""
        if not os.path.exists(self.llm_model_path):
            raise FileNotFoundError(f"Qwen model not found at {self.llm_model_path}")
        model_name = os.path.basename(self.llm_model_path).lower()
        if "qwen" not in model_name:
            logger.warning(f"Model filename '{model_name}' doesn't indicate a Qwen model")
            logger.warning("This module is optimized specifically for Qwen 3.5 models")

    def _initialize_embeddings(self):
        """Initialize the embedding model with caching for improved performance."""
        return HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}  # Improved retrieval with normalized embeddings
        )

    @staticmethod
    def _get_llm_params(enable_thinking: bool) -> dict:
        """Return LlamaCpp sampling parameters for the selected mode."""
        if enable_thinking:
            return {
                "temperature": 1.0,
                "top_p": 0.95,
                "top_k": 20,
                "repeat_penalty": 1.0,
                "min_p": 0.0,
            }
        return {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 20,
            "repeat_penalty": 1.0,
            "min_p": 0.0,
        }

    def _initialize_llm(self):
        """Initialize the Qwen language model with optimized parameters."""
        params = self._get_llm_params(self.enable_thinking)
        extra_model_kwargs = {}
        if self.n_gpu_layers != 0:
            extra_model_kwargs["flash_attn"] = True

        kwargs = {}
        if extra_model_kwargs:
            kwargs["model_kwargs"] = extra_model_kwargs

        return LlamaCpp(
            model_path=self.llm_model_path,
            temperature=params["temperature"],
            max_tokens=768,
            n_ctx=self.context_window,
            n_batch=1024,
            n_threads=self.n_threads,
            n_gpu_layers=self.n_gpu_layers,
            top_p=params["top_p"],
            top_k=params["top_k"],
            repeat_penalty=params["repeat_penalty"],
            stop=["<|im_end|>", "<|im_start|>"],
            verbose=self.verbose,
            **kwargs,
        )

    def _load_documents(self) -> Tuple[List[Document], int]:
        """
        Load documents from the documents directory with parallel processing.

        Returns:
            Tuple of (list of documents, count of source files)
        """
        if self.verbose:
            logger.info(f"Scanning documents in {self.documents_dir}")

        # Discover all files matching supported extensions
        all_files = []
        for ext in SUPPORTED_EXTENSIONS:
            all_files.extend(
                glob.glob(os.path.join(self.documents_dir, f"**/*{ext}"), recursive=True)
            )
        file_count = len(all_files)

        if file_count == 0:
            logger.warning("No documents found in the specified directory.")
            return [], 0

        if self.verbose:
            by_ext = {}
            for f in all_files:
                ext = os.path.splitext(f)[1].lower()
                by_ext[ext] = by_ext.get(ext, 0) + 1
            logger.info(f"Found {file_count} files: {by_ext}")

        def load_file(file_path: str) -> List[Document]:
            ext = os.path.splitext(file_path)[1].lower()
            loader_cls = SUPPORTED_EXTENSIONS.get(ext)
            if loader_cls is None:
                return []
            try:
                return loader_cls(file_path).load()
            except Exception as e:
                logger.warning(f"Error loading {file_path}: {e}")
                return []

        documents = []

        if file_count <= 5:
            for file_path in all_files:
                documents.extend(load_file(file_path))
        else:
            with ThreadPoolExecutor(max_workers=min(self.n_threads, file_count)) as executor:
                for docs in executor.map(load_file, all_files):
                    documents.extend(docs)

        if self.verbose:
            logger.info(f"Loaded {len(documents)} document sections from {file_count} files")

        return documents, file_count

    def _create_vectorstore(self):
        """
        Create an optimized vector store from documents with improved chunking strategy.

        Returns:
            FAISS vector store containing document embeddings
        """
        start_time = time.time()

        # Load documents
        documents, doc_count = self._load_documents()
        self.perf_metrics["doc_count"] = doc_count

        if not documents:
            logger.warning("No documents were successfully loaded.")
            # Create an empty vector store
            empty_texts = ["No documents are available in the corpus."]
            return FAISS.from_texts(empty_texts, self.embeddings)

        # Improved text splitter with better separation strategies
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""],
            length_function=len
        )

        # Split documents into chunks
        chunks = text_splitter.split_documents(documents)
        self.perf_metrics["chunk_count"] = len(chunks)

        if self.verbose:
            logger.info(f"Created {len(chunks)} document chunks in {time.time() - start_time:.2f}s")

        # Deduplicate chunks to save space and improve quality
        chunk_texts = set()
        unique_chunks = []

        for chunk in chunks:
            if chunk.page_content not in chunk_texts:
                chunk_texts.add(chunk.page_content)
                unique_chunks.append(chunk)

        if len(unique_chunks) < len(chunks) and self.verbose:
            logger.info(f"Removed {len(chunks) - len(unique_chunks)} duplicate chunks")

        # Create vector store with optimized parameters
        return FAISS.from_documents(
            unique_chunks,
            self.embeddings
        )

    def _format_context(self, source_documents: List[Document]) -> str:
        """
        Format retrieved documents into a clean, structured context string.

        Args:
            source_documents: List of documents retrieved from the vector store

        Returns:
            Formatted context string optimized for Qwen 3.5
        """
        if not source_documents:
            return "No relevant documents were found."

        context_parts = []

        for i, doc in enumerate(source_documents):
            # Get source information
            source = doc.metadata.get("source", "unknown source")
            source = os.path.basename(source) if "/" in source or "\\" in source else source
            page = doc.metadata.get("page", "")
            page_info = f" (page {page})" if page else ""

            # Format the document section with source attribution but no numbering
            section = f"--- {source}{page_info} ---\n{doc.page_content.strip()}"
            context_parts.append(section)

        # Join with clear separators
        context = "\n\n".join(context_parts)

        # Determine appropriate context length based on model's context window
        # Leaving room for the prompt and response
        max_context_length = min(self.context_window * 0.7, 24000)

        # Truncate if needed with a clean cutoff
        if len(context) > max_context_length:
            # Try to find a clean break point
            cutoff = int(max_context_length)
            while cutoff > max_context_length - 100 and cutoff > 0:
                if context[cutoff] in ".!?\n":
                    break
                cutoff -= 1

            if cutoff <= 0:  # Fallback if no good breakpoint found
                cutoff = int(max_context_length)

            context = context[:cutoff] + "\n\n[Note: Some relevant content was truncated due to length constraints.]"

        return context

    def _retrieve_documents(self, question: str) -> List[Document]:
        """
        Retrieve relevant documents for a question, with caching for performance.

        Args:
            question: The question to find documents for

        Returns:
            List of relevant documents
        """
        if question in self._query_cache:
            return list(self._query_cache[question])

        retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.top_k}
        )

        try:
            docs = retriever.invoke(question)
        except Exception as e:
            logger.error(f"Error during document retrieval: {str(e)}")
            return []

        # Cache with bounded size (evict oldest entry if full)
        if len(self._query_cache) >= 16:
            self._query_cache.pop(next(iter(self._query_cache)))
        self._query_cache[question] = docs
        return list(docs)

    @staticmethod
    def _build_prompt(question: str, context: str, enable_thinking: bool) -> str:
        """Build a ChatML prompt for Qwen 3.5."""
        assistant_suffix = "\n<think>" if enable_thinking else ""
        return f"""<|im_start|>system
You are a research assistant. Answer questions using only the provided documents. Be concise and direct. If the documents don't contain the answer, say so. Do not fabricate quotes or invent information.<|im_end|>
<|im_start|>user
Question: {question}

Documents:
{context}
<|im_end|>
<|im_start|>assistant{assistant_suffix}
"""

    def query(self, question: str) -> Dict[str, Any]:
        """
        Query the RAG system with a question.

        Args:
            question: The question to answer

        Returns:
            Dictionary containing the answer and source documents
        """
        start_time = time.time()
        self.perf_metrics["queries"] += 1

        try:
            # Get source documents using retrieval
            source_documents = self._retrieve_documents(question)

            retrieval_time = time.time() - start_time
            if self.verbose:
                logger.info(f"Retrieved {len(source_documents)} documents in {retrieval_time:.2f}s")

            # Format context from documents
            context = self._format_context(source_documents)

            prompt = self._build_prompt(question, context, self.enable_thinking)
            # Call llama-cpp-python directly to guarantee present_penalty
            # is applied (LangChain's invoke() silently drops it).
            generation_start = time.time()
            p = self._inference_params
            max_tokens = 4096 if self.enable_thinking else 768
            completion = self.llm.client.create_completion(
                prompt,
                max_tokens=max_tokens,
                temperature=p["temperature"],
                top_p=p["top_p"],
                top_k=p["top_k"],
                min_p=p["min_p"],
                repeat_penalty=p["repeat_penalty"],
                present_penalty=1.5,
                stop=["<|im_end|>", "<|im_start|>"],
            )
            raw_answer = completion["choices"][0]["text"]
            generation_time = time.time() - generation_start

            if self.verbose:
                logger.info(f"Generated response in {generation_time:.2f}s")

            # Clean up the answer
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

            total_time = time.time() - start_time
            self.perf_metrics["total_query_time"] += total_time

            if self.verbose:
                logger.info(f"Total query processing time: {total_time:.2f}s")

            return {
                "answer": answer,
                "sources": sources,
                "processing_time": total_time
            }

        except Exception as e:
            logger.error(f"Error querying RAG system: {str(e)}")
            if self.verbose:
                import traceback
                logger.error(traceback.format_exc())

            return {
                "answer": f"I encountered an error while processing your question. Please try again or rephrase your query.",
                "sources": [],
                "processing_time": time.time() - start_time
            }

    def _clean_llm_response(self, response: str) -> str:
        """Clean the LLM response, removing Qwen-specific artifacts."""
        if not response:
            return "I could not generate an answer based on the available documents."

        # Strip thinking blocks.  The prompt may start inside a <think> block
        # (no opening tag in the output), so handle both cases.
        if '</think>' in response:
            # Take only the answer after the thinking block
            response = response.split('</think>', 1)[1]
        elif self.enable_thinking:
            # Thinking mode is on but no </think> found — the model exhausted
            # max_tokens during reasoning and never produced an answer.
            response = ""
        # Clean any remaining complete <think>...</think> pairs
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)

        # Remove Qwen ChatML tags
        response = re.sub(r'<\|im_start\|>[^\n]*\n?', '', response)
        response = re.sub(r'<\|im_end\|>', '', response)
        response = re.sub(r'<\|im_start\|>.*?<\|im_end\|>', '', response, flags=re.DOTALL)

        cleaned = response.strip()

        if not cleaned or len(cleaned) < 10:
            return "I could not generate a meaningful answer based on the available documents."

        # Remove leaked instruction text
        patterns_to_remove = [
            r"^Question:.*?\n",
            r"^Documents:\s*\n",
            r"^---\s+.*?\s+---\s*\n",
            r"^\s*\[Document \d+:.*?\]\s*",
            r"^Based on the provided documents,?\s*",
            r"^According to the provided (?:context|documents),?\s*",
        ]

        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL)

        # Remove document header lines
        lines = cleaned.split('\n')
        filtered_lines = []
        skip_line = False

        for line in lines:
            if re.match(r'^\s*\[Document \d+:', line, re.IGNORECASE):
                skip_line = True
                continue
            if skip_line and not line.strip():
                skip_line = False
                continue
            if not skip_line:
                filtered_lines.append(line)

        cleaned = '\n'.join(filtered_lines)

        # Final formatting cleanup
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r"  +", " ", cleaned)
        cleaned = cleaned.strip()

        if not cleaned or len(cleaned) < 10:
            return "Based on the documents, I could not synthesize a complete answer to your question."

        return cleaned

    def run_interactive(self):
        """Run the RAG system in interactive mode with improved output formatting."""
        print(f"\n===== Qwen 3.5 RAG Chat System =====")
        print(f"Documents: {self.documents_dir}")
        print(f"Model: {os.path.basename(self.llm_model_path)}")
        print(f"Indexed {self.perf_metrics['chunk_count']} chunks from {self.perf_metrics['doc_count']} documents")
        print("Type 'exit' to quit, 'reindex' to refresh documents")
        print("======================================\n")

        while True:
            try:
                user_input = input("\nYou: ").strip()

                if not user_input:
                    continue

                if user_input.lower() == "exit":
                    print("\nExiting. Goodbye!")
                    break

                elif user_input.lower() == "reindex":
                    print("\nReindexing documents...")
                    start_time = time.time()
                    self.vectorstore = self._create_vectorstore()
                    self._query_cache.clear()
                    print(
                        f"Reindexing complete. Processed {self.perf_metrics['chunk_count']} chunks from {self.perf_metrics['doc_count']} documents in {time.time() - start_time:.2f}s")
                    continue

                elif user_input.lower() == "stats":
                    # Show performance statistics
                    avg_query_time = (self.perf_metrics["total_query_time"] / self.perf_metrics["queries"]) if \
                    self.perf_metrics["queries"] > 0 else 0
                    print("\n=== Performance Statistics ===")
                    print(f"Document count: {self.perf_metrics['doc_count']}")
                    print(f"Chunk count: {self.perf_metrics['chunk_count']}")
                    print(f"Indexing time: {self.perf_metrics['indexing_time']:.2f}s")
                    print(f"Queries processed: {self.perf_metrics['queries']}")
                    print(f"Average query time: {avg_query_time:.2f}s")
                    print("============================")
                    continue

                print("\nThinking...")
                result = self.query(user_input)

                # More attractive answer formatting
                print(f"\nAssistant: {result['answer']}")

                # Show processing time for transparency
                print(f"\n(Processed in {result['processing_time']:.2f}s)")

                if result['sources']:
                    print("\nSources:")
                    # Deduplicate and limit sources for clarity
                    unique_sources = {}

                    for source in result['sources']:
                        source_text = os.path.basename(source['source'])
                        if source.get('page') is not None:
                            key = f"{source_text}:{source['page']}"
                        else:
                            key = source_text

                        unique_sources[key] = source

                    # Print deduplicated sources
                    for i, (_, source) in enumerate(unique_sources.items(), 1):
                        source_text = os.path.basename(source['source'])
                        if source.get('page') is not None:
                            source_text += f" (page {source['page']})"
                        print(f"{i}. {source_text}")

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'exit' to quit or press Enter to continue.")
                continue

            except Exception as e:
                print(f"\nError: {str(e)}")
                if self.verbose:
                    import traceback
                    print(traceback.format_exc())


def main():
    """Main function with improved argument handling and error recovery."""
    parser = argparse.ArgumentParser(
        description="Qwen 3.5 RAG Chat System",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--documents",
        default="./documents",
        help="Directory containing documents"
    )

    parser.add_argument(
        "--llm",
        default="./models/Qwen3.5-4B-Q4_K_M.gguf",
        help="Path to Qwen 3.5 model file (.gguf)"
    )

    parser.add_argument(
        "--embeddings",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Name of embedding model to use"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Size of document chunks for indexing"
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=64,
        help="Overlap between document chunks"
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=15,
        help="Number of chunks to retrieve per query"
    )

    parser.add_argument(
        "--threads",
        type=int,
        default=4,
        help="Number of threads to use for processing"
    )

    parser.add_argument(
        "--context-window",
        type=int,
        default=32768,
        help="Context window size for the Qwen 3.5 model"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--enable-thinking",
        action="store_true",
        help="Enable chain-of-thought thinking mode"
    )

    parser.add_argument(
        "--gpu-layers",
        type=int,
        default=0,
        help="Number of layers to offload to GPU (-1 for all, 0 for CPU only)"
    )

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
            print(f"Please download an appropriate Qwen model or specify the correct path with --llm")
            return

        # Initialize the RAG system
        rag_system = QwenRAGSystem(
            documents_dir=args.documents,
            llm_model_path=args.llm,
            embedding_model_name=args.embeddings,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            top_k=args.top_k,
            n_threads=args.threads,
            context_window=args.context_window,
            verbose=args.verbose,
            enable_thinking=args.enable_thinking,
            n_gpu_layers=args.gpu_layers
        )

        # Run the interactive chat
        rag_system.run_interactive()

    except KeyboardInterrupt:
        print("\nExiting on user interrupt.")

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
