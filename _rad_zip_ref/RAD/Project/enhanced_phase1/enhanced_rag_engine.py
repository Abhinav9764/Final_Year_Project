"""
Enhanced RAG Engine with Web Content Integration
Generates structured, comprehensive responses with code examples
"""

import json
import numpy as np
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import re

try:
    import faiss
    HAS_FAISS = True
except Exception:
    faiss = None
    HAS_FAISS = False

class EnhancedRAGEngine:
    """
    Advanced RAG engine with:
    - Web content integration
    - Structured output generation
    - Code example generation
    - Multi-source document retrieval
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        web_fetcher=None,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        generation_model: str = "microsoft/phi-2"
    ):
        """
        Initialize enhanced RAG engine
        
        Args:
            config: Configuration dictionary
            web_fetcher: WebContentFetcher instance
            embedding_model: Model for embeddings
            generation_model: Model for generation
        """
        self.config = config
        self.web_fetcher = web_fetcher
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        print(f"Initializing Enhanced RAG Engine on {self.device}...")
        
        # Initialize embedding model
        print(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Initialize generation model
        print(f"Loading generation model: {generation_model}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                generation_model,
                trust_remote_code=True
            )
            self.gen_model = AutoModelForCausalLM.from_pretrained(
                generation_model,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                trust_remote_code=True,
                device_map="auto" if self.device == "cuda" else None
            )
            
            if self.device == "cpu":
                self.gen_model = self.gen_model.to(self.device)
            
            self.model_loaded = True
            print("[OK] Generation model loaded successfully!")
            
        except Exception as e:
            print(f"[WARN] Could not load generation model: {e}")
            print("-> Using template-based generation")
            self.model_loaded = False
        
        # Initialize storage
        self.vector_store = None
        self._embeddings = None
        self.documents = []
        self.last_retrieved_docs = []
        
        # Load knowledge base
        self._initialize_knowledge_base()
    
    def _initialize_knowledge_base(self):
        """Initialize with enhanced knowledge base"""
        
        default_docs = self.config.get('ENHANCED_KNOWLEDGE_BASE', [])
        
        if self.config.get('USE_DEFAULT_DOCUMENTS', True):
            self.add_documents(default_docs)
            print(f"[OK] Loaded {len(default_docs)} default documents")
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        """Add documents to the knowledge base"""
        
        self.documents.extend(documents)
        
        # Create embeddings
        contents = [doc["content"] for doc in documents]
        embeddings = self.embedding_model.encode(contents)
        emb = np.array(embeddings)
        if emb.ndim == 1:
            emb = emb.reshape(1, -1)
        emb = emb.astype('float32')
        
        # Update vector store
        if HAS_FAISS:
            dimension = emb.shape[1]
            if self.vector_store is None:
                self.vector_store = faiss.IndexFlatL2(dimension)
            self.vector_store.add(emb)
        else:
            if self._embeddings is None:
                self._embeddings = emb
            else:
                self._embeddings = np.vstack([self._embeddings, emb])
        
        print(f"[OK] Added {len(documents)} documents (Total: {len(self.documents)})")
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant documents"""
        
        if not self.documents:
            return []
        
        # Create query embedding
        query_embedding = self.embedding_model.encode([query])
        q = np.array(query_embedding).astype('float32')
        if q.ndim == 1:
            q = q.reshape(1, -1)
        
        results = []
        
        if HAS_FAISS and self.vector_store is not None:
            distances, indices = self.vector_store.search(
                q,
                min(top_k, len(self.documents))
            )
            
            for idx, distance in zip(indices[0], distances[0]):
                if idx < len(self.documents):
                    doc = self.documents[idx].copy()
                    doc['score'] = float(1 / (1 + distance))
                    results.append(doc)
        else:
            # NumPy fallback
            if self._embeddings is None:
                return []
            
            emb = self._embeddings
            emb_norm = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-10)
            q_norm = q / (np.linalg.norm(q, axis=1, keepdims=True) + 1e-10)
            sims = (emb_norm @ q_norm.T).reshape(-1)
            
            k = min(top_k, len(self.documents))
            idxs = np.argsort(-sims)[:k]
            for idx in idxs:
                doc = self.documents[idx].copy()
                doc['score'] = float(sims[idx])
                results.append(doc)
        
        self.last_retrieved_docs = results
        return results
    
    def generate_response(
        self,
        prompt: str,
        analysis: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        top_k: int = 5
    ) -> str:
        """
        Generate comprehensive structured response
        
        Args:
            prompt: User prompt
            analysis: Prompt analysis from analyzer
            temperature: Generation temperature
            max_tokens: Maximum tokens
            top_k: Number of documents to retrieve
            
        Returns:
            Structured response
        """
        print("\n[INFO] Starting response generation...")
        
        # Step 1: Retrieve default documents
        print("[INFO] Retrieving from knowledge base...")
        default_docs = self.retrieve(prompt, top_k=top_k)
        
        # Step 2: Fetch web content if enabled
        web_docs = []
        if self.config.get('USE_WEB_CONTENT', True) and self.web_fetcher:
            print("[INFO] Fetching web content...")
            
            search_queries = analysis.get('web_search_queries', [])
            if not search_queries:
                search_queries = [prompt]
            
            for query in search_queries[:2]:  # Limit to 2 queries
                web_content = self.web_fetcher.fetch_content(
                    query,
                    max_pages=self.config.get('MAX_WEB_PAGES_PER_QUERY', 3)
                )
                web_docs.extend(web_content)
            
            # Add web documents to knowledge base temporarily
            if web_docs:
                print(f"[OK] Retrieved {len(web_docs)} web documents")
                self.add_documents(web_docs)
        
        # Step 3: Combine all documents
        all_docs = default_docs + web_docs
        
        # Re-rank by relevance
        all_docs.sort(key=lambda x: x.get('score', 0), reverse=True)
        relevant_docs = all_docs[:top_k]
        
        # Step 4: Build context
        context = self._build_enhanced_context(relevant_docs, analysis)
        
        # Step 5: Generate structured response
        print("[INFO] Generating structured response...")
        
        if analysis.get('is_generation_request', False):
            response = self._generate_structured_response(
                prompt=prompt,
                context=context,
                analysis=analysis,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            response = self._generate_standard_response(
                prompt=prompt,
                context=context,
                analysis=analysis,
                temperature=temperature,
                max_tokens=max_tokens
            )
        
        return response
    
    def _build_enhanced_context(
        self,
        documents: List[Dict[str, Any]],
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build enhanced context from documents"""
        
        context = {
            "documents": [],
            "sources": [],
            "key_information": {
                "algorithms": [],
                "datasets": [],
                "implementations": [],
                "concepts": []
            }
        }
        
        for doc in documents:
            doc_info = {
                "content": doc.get('content', ''),
                "source": doc.get('metadata', {}).get('source', 'unknown'),
                "score": doc.get('score', 0)
            }
            context["documents"].append(doc_info)
            
            # Extract source
            source = doc.get('metadata', {}).get('source', 'Unknown')
            if source not in context["sources"]:
                context["sources"].append(source)
            
            # Extract key information
            content = doc.get('content', '').lower()
            
            # Algorithms
            algo_patterns = r'([\w\s]+(?:algorithm|method|approach|technique))'
            algos = re.findall(algo_patterns, content)
            context["key_information"]["algorithms"].extend(algos[:3])
            
            # Datasets
            dataset_patterns = r'([\w\s]+(?:dataset|data|corpus))'
            datasets = re.findall(dataset_patterns, content)
            context["key_information"]["datasets"].extend(datasets[:3])
        
        # Remove duplicates
        for key in context["key_information"]:
            context["key_information"][key] = list(set(context["key_information"][key]))[:5]
        
        return context
    
    def _generate_structured_response(
        self,
        prompt: str,
        context: Dict[str, Any],
        analysis: Dict[str, Any],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate structured response for generation requests"""
        
        parameters = analysis.get('parameters', {})
        main_topic = parameters.get('main_topic', 'the requested topic')
        subject = parameters.get('subject', '')
        
        # Build structured response
        sections = []
        
        # TITLE
        sections.append(f"# {main_topic.title()}\n")
        
        # CONTEXT
        sections.append("## 📋 Context\n")
        context_text = self._generate_context_section(subject, context)
        sections.append(context_text + "\n")
        
        # ALGORITHMS
        sections.append("## 🧮 Algorithms and Approaches\n")
        algorithms_text = self._generate_algorithms_section(subject, context)
        sections.append(algorithms_text + "\n")
        
        # DATASET INFO
        sections.append("## 📊 Dataset Information\n")
        dataset_text = self._generate_dataset_section(subject, context)
        sections.append(dataset_text + "\n")
        
        # SAMPLE CODE
        sections.append("## 💻 Sample Implementation\n")
        code_text = self._generate_code_section(subject, context, analysis)
        sections.append(code_text + "\n")
        
        # DETAILED EXPLANATION
        sections.append("## 📖 Detailed Explanation\n")
        explanation_text = self._generate_explanation_section(subject, context)
        sections.append(explanation_text + "\n")
        
        # SOURCES
        if context.get('sources'):
            sections.append("## 📚 Sources\n")
            for source in context['sources'][:5]:
                sections.append(f"- {source}\n")
        
        return '\n'.join(sections)
    
    def _generate_context_section(self, subject: str, context: Dict[str, Any]) -> str:
        """Generate context section"""
        
        # Extract relevant information from documents
        doc_contents = [doc['content'] for doc in context.get('documents', [])[:3]]
        
        if not doc_contents:
            return f"A {subject} system is designed to analyze data and provide predictions or recommendations based on patterns learned from historical data."
        
        # Combine and summarize
        combined = ' '.join(doc_contents[:500])  # Limit length
        
        # Extract key sentences
        sentences = re.split(r'[.!?]+', combined)
        relevant_sentences = [s.strip() for s in sentences if subject.lower() in s.lower()][:3]
        
        if relevant_sentences:
            return ' '.join(relevant_sentences) + '.'
        else:
            return ' '.join(sentences[:3]) + '.'
    
    def _generate_algorithms_section(self, subject: str, context: Dict[str, Any]) -> str:
        """Generate algorithms section"""
        
        algorithms = context.get('key_information', {}).get('algorithms', [])
        
        if not algorithms:
            # Provide default algorithms based on subject
            if 'recommendation' in subject.lower():
                algorithms = [
                    "Collaborative Filtering",
                    "Content-Based Filtering",
                    "Matrix Factorization",
                    "Neural Collaborative Filtering"
                ]
            elif 'classification' in subject.lower():
                algorithms = [
                    "Logistic Regression",
                    "Random Forest",
                    "Support Vector Machines",
                    "Neural Networks"
                ]
            else:
                algorithms = [
                    "Supervised Learning algorithms",
                    "Deep Learning approaches",
                    "Ensemble methods"
                ]
        
        text = f"Common algorithms for {subject} include:\n\n"
        for i, algo in enumerate(algorithms[:5], 1):
            text += f"{i}. **{algo.strip().title()}**: Effective for pattern recognition and prediction\n"
        
        return text
    
    def _generate_dataset_section(self, subject: str, context: Dict[str, Any]) -> str:
        """Generate dataset section"""
        
        datasets = context.get('key_information', {}).get('datasets', [])
        
        text = f"For building a {subject} system, you'll need:\n\n"
        text += "**Dataset Requirements:**\n"
        
        if 'recommendation' in subject.lower():
            text += "- User-item interaction data (ratings, clicks, purchases)\n"
            text += "- User demographics (optional)\n"
            text += "- Item features and metadata\n"
            text += "- Temporal information (timestamps)\n\n"
            text += "**Popular Datasets:**\n"
            text += "- MovieLens (movie ratings)\n"
            text += "- Amazon Product Reviews\n"
            text += "- Netflix Prize Dataset\n"
        elif 'classification' in subject.lower():
            text += "- Labeled training data\n"
            text += "- Feature vectors\n"
            text += "- Validation and test sets\n"
        else:
            text += "- Historical data with relevant features\n"
            text += "- Labeled examples for supervised learning\n"
            text += "- Sufficient data volume for training\n"
        
        text += "\n*Note: Dataset generation capabilities will be available in Phase 2.*"
        
        return text
    
    def _generate_code_section(
        self,
        subject: str,
        context: Dict[str, Any],
        analysis: Dict[str, Any]
    ) -> str:
        """Generate sample code section"""
        
        # Generate code based on subject
        if 'recommendation' in subject.lower():
            code = self._generate_recommendation_code(subject)
        elif 'classification' in subject.lower():
            code = self._generate_classification_code(subject)
        elif 'clustering' in subject.lower():
            code = self._generate_clustering_code(subject)
        else:
            code = self._generate_generic_ml_code(subject)
        
        return f"```python\n{code}\n```\n"
    
    def _generate_recommendation_code(self, subject: str) -> str:
        """Generate recommendation system code"""
        
        return '''# Movie Recommendation System using Collaborative Filtering
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse import csr_matrix

class MovieRecommender:
    def __init__(self):
        self.user_item_matrix = None
        self.item_similarity = None
        
    def fit(self, ratings_df):
        """
        Train the recommendation model
        
        Args:
            ratings_df: DataFrame with columns [user_id, movie_id, rating]
        """
        # Create user-item matrix
        self.user_item_matrix = ratings_df.pivot_table(
            index='user_id',
            columns='movie_id',
            values='rating',
            fill_value=0
        )
        
        # Calculate item-item similarity
        item_matrix = self.user_item_matrix.T
        self.item_similarity = cosine_similarity(item_matrix)
        
        print(f"Model trained on {len(self.user_item_matrix)} users and {len(item_matrix)} movies")
        
    def recommend(self, user_id, n_recommendations=10):
        """
        Generate recommendations for a user
        
        Args:
            user_id: User ID
            n_recommendations: Number of recommendations
            
        Returns:
            List of recommended movie IDs
        """
        if user_id not in self.user_item_matrix.index:
            return []
        
        # Get user's ratings
        user_ratings = self.user_item_matrix.loc[user_id]
        
        # Calculate weighted ratings
        weighted_ratings = np.dot(self.item_similarity.T, user_ratings)
        
        # Normalize by similarity sum
        similarity_sums = np.sum(np.abs(self.item_similarity), axis=1)
        predicted_ratings = weighted_ratings / (similarity_sums + 1e-10)
        
        # Get top recommendations (exclude already rated)
        rated_mask = user_ratings > 0
        predicted_ratings[rated_mask] = -np.inf
        
        top_indices = np.argsort(predicted_ratings)[-n_recommendations:][::-1]
        recommended_movies = self.user_item_matrix.columns[top_indices]
        
        return recommended_movies.tolist()

# Example usage
if __name__ == "__main__":
    # Sample data
    data = {
        'user_id': [1, 1, 1, 2, 2, 3, 3, 3],
        'movie_id': [101, 102, 103, 101, 104, 102, 103, 104],
        'rating': [5, 4, 3, 4, 5, 5, 4, 3]
    }
    
    df = pd.DataFrame(data)
    
    # Train model
    recommender = MovieRecommender()
    recommender.fit(df)
    
    # Get recommendations
    recommendations = recommender.recommend(user_id=1, n_recommendations=5)
    print(f"Recommended movies: {recommendations}")
'''
    
    def _generate_classification_code(self, subject: str) -> str:
        """Generate classification code"""
        
        return '''# Classification Model Example
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import pandas as pd

class Classifier:
    def __init__(self, n_estimators=100):
        self.model = RandomForestClassifier(n_estimators=n_estimators, random_state=42)
        
    def train(self, X, y):
        """Train the classifier"""
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        self.model.fit(X_train, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Test Accuracy: {accuracy:.4f}")
        print(classification_report(y_test, y_pred))
        
    def predict(self, X):
        """Make predictions"""
        return self.model.predict(X)

# Example usage
# classifier = Classifier()
# classifier.train(X_features, y_labels)
'''
    
    def _generate_clustering_code(self, subject: str) -> str:
        """Generate clustering code"""
        
        return '''# Clustering Example using K-Means
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import numpy as np

class Clusterer:
    def __init__(self, n_clusters=3):
        self.scaler = StandardScaler()
        self.model = KMeans(n_clusters=n_clusters, random_state=42)
        
    def fit(self, X):
        """Fit clustering model"""
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        return self.model.labels_
        
    def predict(self, X):
        """Predict cluster for new data"""
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
'''
    
    def _generate_generic_ml_code(self, subject: str) -> str:
        """Generate generic ML code"""
        
        return '''# Generic Machine Learning Pipeline
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score

class MLModel:
    def __init__(self):
        self.scaler = StandardScaler()
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        
    def train(self, X, y):
        """Train the model"""
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train
        self.model.fit(X_train_scaled, y_train)
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        print(f"MSE: {mse:.4f}")
        print(f"R² Score: {r2:.4f}")
        
    def predict(self, X):
        """Make predictions"""
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
'''
    
    def _generate_explanation_section(self, subject: str, context: Dict[str, Any]) -> str:
        """Generate detailed explanation section"""
        
        text = f"### How the {subject.title()} System Works:\n\n"
        
        if 'recommendation' in subject.lower():
            text += """**1. Data Collection:**
- Gather user-item interaction data (ratings, purchases, clicks)
- Collect item features and user demographics
- Store data in structured format

**2. Data Preprocessing:**
- Handle missing values and outliers
- Normalize ratings if needed
- Create user-item interaction matrix
- Split data into train/test sets

**3. Model Training:**
- Apply collaborative filtering or content-based approaches
- Calculate similarity between users or items
- Learn latent factors using matrix factorization
- Train neural networks for deep learning approaches

**4. Generating Recommendations:**
- For a given user, find similar users or items
- Predict ratings for unseen items
- Rank items by predicted ratings
- Return top-N recommendations

**5. Evaluation:**
- Measure accuracy (RMSE, MAE)
- Assess ranking quality (Precision@K, Recall@K)
- Evaluate diversity and novelty
- Perform A/B testing

**6. Deployment:**
- Integrate model into production system
- Implement real-time recommendation serving
- Monitor performance and retrain periodically
"""
        else:
            text += """**1. Problem Definition:**
Define the task, identify input features, and determine target variable.

**2. Data Preparation:**
Collect data, handle missing values, encode categorical variables, and split into train/test sets.

**3. Feature Engineering:**
Create new features, select relevant ones, and scale/normalize data.

**4. Model Selection:**
Choose appropriate algorithms, compare different approaches, and tune hyperparameters.

**5. Training:**
Fit the model on training data, validate performance, and prevent overfitting.

**6. Evaluation:**
Test on unseen data, calculate metrics, and analyze results.

**7. Deployment:**
Deploy model to production, monitor performance, and update as needed.
"""
        
        return text
    
    def _generate_standard_response(
        self,
        prompt: str,
        context: Dict[str, Any],
        analysis: Dict[str, Any],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate standard response for non-generation requests"""
        
        # Build response from context
        sections = []
        
        # Add main content from documents
        doc_contents = [doc['content'] for doc in context.get('documents', [])[:3]]
        
        if doc_contents:
            sections.append('\n\n'.join(doc_contents[:2]))
        else:
            sections.append("I don't have specific information in my knowledge base to answer this question comprehensively.")
        
        # Add sources
        sources = context.get('sources', [])
        if sources:
            sections.append(f"\n\n**Sources:** {', '.join(sources[:5])}")
        
        return '\n'.join(sections)
