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
from qdrant_client.models import VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.core import logger, ExpenseLearner
from tqdm import tqdm


class QdrantExpenseLearner:
    """Expense classifier using vector embeddings and Qdrant"""

    def __init__(self, db_manager, collection_name="expenses"):
        self.db_manager = db_manager
        # Załaduj model embeddings
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_size = self.embedding_model.get_sentence_embedding_dimension()
        self.min_samples_per_category = 3

        # Połącz z Qdrant
        self.client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        self.collection_name = collection_name

        # Sprawdź czy kolekcja istnieje, jeśli nie - utwórz
        collections = self.client.get_collections().collections
        collection_names = [c.name for c in collections]

        if collection_name not in collection_names:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
            )

    def _get_text_embedding(self, text):
        """Konwertuj tekst na wektor"""
        return self.embedding_model.encode(text)

    def _prepare_expense_text(self, expense):
        """Przygotuj tekst wydatku do wektoryzacji"""
        text = f"{expense.get('transcription', '')} {expense.get('vendor', '')} {expense.get('description', '')}"
        return text.strip()

    def train_model(self):
        """Trenuj model wektorowy na podstawie danych historycznych"""
        try:
            expenses = self.db_manager.get_all_expenses_for_training()

            if not expenses or len(expenses) < 10:
                logger.warning("Not enough data to train model (minimum 10 expenses required)")
                return False

            # Przygotuj punkty do załadowania do Qdrant
            points = []

            # Tworzy DataFrame dla walidacji krzyżowej
            df = pd.DataFrame(expenses)

            # Sprawdź liczbę próbek na kategorię
            category_counts = df['category'].value_counts()
            valid_categories = category_counts[category_counts >= self.min_samples_per_category].index.tolist()

            if len(valid_categories) < 2:
                logger.warning(f"Not enough categories with sufficient samples (min {self.min_samples_per_category})")
                return False

            # Filtruj tylko kategorie z wystarczającą liczbą próbek
            df = df[df['category'].isin(valid_categories)]

            # Ocena dokładności przez walidację krzyżową
            kf = KFold(n_splits=5, shuffle=True, random_state=42)
            accuracies = []

            for train_idx, test_idx in kf.split(df):
                train_df = df.iloc[train_idx]
                test_df = df.iloc[test_idx]

                # Trenuj na zbiorze treningowym (dodaj do tymczasowej kolekcji)
                temp_collection = f"temp_{uuid.uuid4().hex[:8]}"
                try:
                    self.client.create_collection(
                        collection_name=temp_collection,
                        vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                    )

                    # Dodaj dane treningowe
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

                    # Testuj na zbiorze testowym
                    correct = 0
                    for _, expense in test_df.iterrows():
                        text = self._prepare_expense_text(expense)
                        vector = self._get_text_embedding(text)

                        results = self.client.search(
                            collection_name=temp_collection,
                            query_vector=vector.tolist(),
                            limit=3
                        )

                        if results:
                            # Głosowanie ważone
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
                    # Usuń tymczasową kolekcję
                    try:
                        self.client.delete_collection(collection_name=temp_collection)
                    except:
                        pass

            # Oblicz średnią dokładność
            mean_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0

            # Loguj obliczoną dokładność
            logger.info(f"Vector model metrics calculated: accuracy={mean_accuracy:.4f}")

            # Teraz upsert wszystkich punktów do głównej kolekcji
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

            # Upsert punktów do kolekcji
            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )

            # Przygotuj i zapisz metryki
            metrics = {
                'accuracy': mean_accuracy,
                'samples_count': len(df),
                'categories_count': len(valid_categories),
                'confusion_matrix': [],  # Puste dla wektorów
                'confusion_labels': valid_categories,
                'top_features': {},
                'cv_scores': accuracies
            }

            # Zapisz metryki
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
        """Przewiduj kategorię wydatku na podstawie podobieństwa wektorowego"""
        # Przygotuj tekst i wektor zapytania
        query_text = f"{transcription} {vendor or ''} {description or ''}"
        query_vector = self._get_text_embedding(query_text)

        # Wyszukaj podobne wydatki
        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=5  # Znajdź 5 najbardziej podobnych wydatków
        )

        if not search_results:
            return None

        # Głosowanie ważone - każdy wynik ma wagę proporcjonalną do podobieństwa
        category_scores = {}
        for result in search_results:
            category = result.payload['category']
            similarity = result.score  # Podobieństwo kosinusowe

            category_scores[category] = category_scores.get(category, 0) + similarity

        # Zwróć kategorię z najwyższym wynikiem
        if category_scores:
            return max(category_scores.items(), key=lambda x: x[1])[0]
        return None

    def predict_category_with_confidence(self, transcription, vendor=None, description=None):
        """Przewiduj kategorię z poziomem pewności"""
        query_text = f"{transcription} {vendor or ''} {description or ''}"
        query_vector = self._get_text_embedding(query_text)

        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=5
        )

        if not search_results:
            return None, 0.0

        # Oblicz wyniki dla kategorii
        category_scores = {}
        for result in search_results:
            category = result.payload['category']
            similarity = result.score

            category_scores[category] = category_scores.get(category, 0) + similarity

        # Normalizuj wyniki do sumy 1.0
        total_score = sum(category_scores.values())
        if total_score > 0:
            for category in category_scores:
                category_scores[category] /= total_score

        # Znajdź najlepszą kategorię i jej pewność
        if category_scores:
            best_category = max(category_scores.items(), key=lambda x: x[1])
            return best_category[0], best_category[1]

        return None, 0.0

    def incremental_train(self, expense_id, confirmed_category):
        """Przyrostowe uczenie modelu - dodaj nowy punkt lub zaktualizuj istniejący"""
        expense = self.db_manager.get_expense(expense_id)
        if not expense:
            logger.warning(f"Cannot incrementally train - expense ID {expense_id} not found")
            return False

        # Przygotuj tekst i wektor
        text = self._prepare_expense_text(expense)
        vector = self._get_text_embedding(text)

        # Upsert pojedynczego punktu
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