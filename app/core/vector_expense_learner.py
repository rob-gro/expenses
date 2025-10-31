import pandas as pd
import uuid
import os
import numpy as np
from sklearn import metrics
from tqdm import tqdm
from sklearn.model_selection import KFold
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB

# Conditional imports for heavy modules
try:
    if not os.environ.get('DISABLE_HEAVY_MODULES'):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PointStruct
        from sentence_transformers import SentenceTransformer
        QDRANT_AVAILABLE = True
    else:
        QDRANT_AVAILABLE = False
        QdrantClient = None
        SentenceTransformer = None
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None
    SentenceTransformer = None

from app.core import logger, ExpenseLearner


class QdrantExpenseLearner:
    """Expense classifier using vector embeddings and Qdrant"""

    def __init__(self, db_manager, collection_name="expenses"):
        if not QDRANT_AVAILABLE:
            logger.warning("Qdrant and SentenceTransformers not available - vector learning disabled")
            raise ImportError("qdrant_client or sentence_transformers not installed")

        self.db_manager = db_manager
        # Load embeddings model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_size = self.embedding_model.get_sentence_embedding_dimension()
        self.min_samples_per_category = 5

        # Connect to Qdrant
        self.client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        self.collection_name = collection_name

        # Check if collection exists, if not - create it
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if collection_name not in collection_names:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )

    def _get_text_embedding(self, text):
        """Convert text to vector"""
        return self.embedding_model.encode(text)

    def _prepare_expense_text(self, expense):
        """Prepare expense text for vectorization"""
        text = f"{expense.get('transcription', '')} {expense.get('vendor', '')} {expense.get('description', '')}"
        return text.strip()

    def train_model(self):
        """Train vector model based on historical data"""
        try:
            expenses = self.db_manager.get_all_expenses_for_training()

            if not expenses or len(expenses) < 10:
                logger.warning("Not enough data to train model (minimum 10 expenses required)")
                return False

            # Prepare points to load into Qdrant
            points = []

            # Create DataFrame for cross validation
            df = pd.DataFrame(expenses)

            # Check number of samples per category
            category_counts = df['category'].value_counts()
            valid_categories = category_counts[category_counts >= self.min_samples_per_category].index.tolist()

            if len(valid_categories) < 2:
                logger.warning(f"Not enough categories with sufficient samples (min {self.min_samples_per_category})")
                return False

            # Filter only categories with sufficient number of samples
            df = df[df['category'].isin(valid_categories)]

            # Evaluate accuracy through cross validation
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            accuracies = []

            for train_idx, test_idx in kf.split(df):
                train_df = df.iloc[train_idx]
                test_df = df.iloc[test_idx]

                # Train on the training set (add to temporary collection)
                temp_collection = f"temp_{uuid.uuid4().hex[:8]}"
                try:
                    self.client.create_collection(
                        collection_name=temp_collection,
                        vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                    )

                    # Add training data
                    train_points = []
                    for _, expense in train_df.iterrows():
                        text = self._prepare_expense_text(expense)
                        vector = self._get_text_embedding(text)
                        train_points.append(PointStruct(
                            id=len(train_points),
                            vector=vector.tolist(),
                            payload={'category': expense['category']}
                        ))

                    if train_points:
                        self.client.upsert(collection_name=temp_collection, points=train_points)

                    # Test on the test set
                    correct = 0
                    for _, expense in test_df.iterrows():
                        text = self._prepare_expense_text(expense)
                        vector = self._get_text_embedding(text)

                        results = self.client.search(
                            collection_name=temp_collection,
                            query_vector=vector.tolist(),
                            limit=7
                        )

                        if results:
                            # Weighted voting
                            categories = {}
                            for res in results:
                                cat = res.payload['category']
                                score = res.score
                                categories[cat] = categories.get(cat, 0) + score

                            if categories:
                                predicted = max(categories.items(), key=lambda x: x[1])[0]
                                if predicted == expense['category']:
                                    correct += 1

                    accuracy = correct / len(test_df) if len(test_df) > 0 else 0
                    accuracies.append(accuracy)

                finally:
                    # Remove temporary collection
                    try:
                        self.client.delete_collection(collection_name=temp_collection)
                    except:
                        pass

            # Calculate average accuracy
            mean_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0

            # Log calculated accuracy
            logger.info(f"Vector model metrics calculated: accuracy={mean_accuracy:.4f}")

            # Now upsert all points to main collection
            for idx, expense in enumerate(expenses):
                if expense['category'] in valid_categories:
                    text = self._prepare_expense_text(expense)
                    vector = self._get_text_embedding(text)

                    points.append(PointStruct(
                        id=expense['id'],
                        vector=vector.tolist(),
                        payload={
                            'category': expense['category'],
                            'amount': float(expense['amount']),
                            'date': expense['date'].isoformat() if hasattr(expense['date'], 'isoformat') else expense[
                                'date']
                        }
                    ))

            # Upsert points to collection
            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )

            # Prepare and save metrics
            metrics = {
                'accuracy': mean_accuracy,
                'samples_count': len(df),
                'categories_count': len(valid_categories),
                'confusion_matrix': [],  # Empty for vectors
                'confusion_labels': valid_categories,
                'top_features': {},
                'cv_scores': accuracies
            }

            # Save metrics
            logger.info("Saving metrics to database...")
            dummy_learner = ExpenseLearner(self.db_manager)
            result = dummy_learner.save_metrics(metrics, "vector", "Vector model training")
            logger.info(f"Metrics saved to database: {result}")

            logger.info(f"Successfully trained model on {len(df)} expenses across {len(valid_categories)} categories")
            logger.info(f"Cross-validation accuracy: {mean_accuracy:.4f}")
            return True

        except Exception as e:
            logger.error(f"Error training vector model: {str(e)}", exc_info=True)
            return False

    def predict_category(self, transcription, vendor=None, description=None):
        """Predict expense category based on vector similarity"""
        # Prepare the text and query vector
        query_text = f"{transcription} {vendor or ''} {description or ''}"
        query_vector = self._get_text_embedding(query_text)

        # Search for similar expenses
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=5  # Find 5 most similar expenses
        )

        if not search_results:
            return None

        # Weighted voting - each result has weight proportional to similarity
        category_scores = {}
        for result in search_results:
            category = result.payload['category']
            similarity = result.score  # Cosine similarity

            category_scores[category] = category_scores.get(category, 0) + similarity

        # Return category with the highest score
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        return None

    def predict_category_with_confidence(self, transcription, vendor=None, description=None):
        """Predict category with confidence level"""
        query_text = f"{transcription} {vendor or ''} {description or ''}"
        query_vector = self._get_text_embedding(query_text)

        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=5
        )

        if not search_results:
            return None, 0.0

        # Calculate scores for categories
        category_scores = {}
        for result in search_results:
            category = result.payload['category']
            similarity = result.score

            category_scores[category] = category_scores.get(category, 0) + similarity

        # Normalize results to sum 1.0
        total_score = sum(category_scores.values())
        if total_score > 0:
            for category in category_scores:
                category_scores[category] /= total_score

        # Find the best category and its confidence
        if category_scores:
            best_category = max(category_scores.items(), key=lambda x: x[1])
            return best_category[0], best_category[1]

        return None, 0.0

    def incremental_train(self, expense_id, confirmed_category):
        """Incremental model training - add new point or update existing one"""
        expense = self.db_manager.get_expense(expense_id)
        if not expense:
            logger.warning(f"Cannot incrementally train - expense ID {expense_id} not found")
            return False

        # Prepare text and vector
        text = self._prepare_expense_text(expense)
        vector = self._get_text_embedding(text)

        # Upsert a single record
        self.client.upsert(
            collection_name=self.collection_name,
            points=[PointStruct(
                id=expense_id,
                vector=vector.tolist(),
                payload={
                    'category': confirmed_category,
                    'amount': float(expense['amount']),
                    'date': expense['date'].isoformat() if hasattr(expense['date'], 'isoformat') else expense['date']
                }
            )]
        )

        logger.info(f"Successfully updated model incrementally with expense ID {expense_id}")
        return True

    def save_model(self):
        """
        Placeholder method for compatibility with traditional model.
        Vector model doesn't need to be saved as data is already in Qdrant.
        """
        logger.info("Vector model data already stored in Qdrant - no need to save locally")
        return True