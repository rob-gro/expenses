import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
import pickle
import os
import logging

logger = logging.getLogger(__name__)


class ExpenseLearner:
    """Learn from past expenses to predict categories for new ones"""

    def __init__(self, db_manager, model_path='models/expense_classifier.pkl'):
        self.db_manager = db_manager
        self.model_path = model_path
        self.model = None
        self.min_samples_per_category = 3

        os.makedirs(os.path.dirname(model_path), exist_ok=True)

        self.load_model()

    def load_model(self):
        """Load trained model if exists"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    self.model = pickle.load(f)
                logger.info(f"Loaded expense classifier model from {self.model_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            return False

    def save_model(self):
        """Save model to disk"""
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            logger.info(f"Saved expense classifier model to {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
            return False

    def train_model(self):
        """Train model on historical expense data"""
        try:
            # Pobierz dane historyczne z bazy
            expenses = self.db_manager.get_all_expenses_for_training()

            if not expenses or len(expenses) < 10:  # Minimalny próg do szkolenia
                logger.warning("Not enough data to train model (minimum 10 expenses required)")
                return False

            # Konwertuj do DataFrame
            df = pd.DataFrame(expenses)

            # Sprawdź liczbę próbek na kategorię
            category_counts = df['category'].value_counts()
            valid_categories = category_counts[category_counts >= self.min_samples_per_category].index.tolist()

            if len(valid_categories) < 2:  # Potrzebujemy przynajmniej 2 kategorie
                logger.warning(f"Not enough categories with sufficient samples (min {self.min_samples_per_category})")
                return False

            # Filtruj tylko kategorie z wystarczającą liczbą próbek
            df = df[df['category'].isin(valid_categories)]

            # Połącz transkrypcję i opis sprzedawcy dla lepszych cech
            df['features'] = df['transcription'] + ' ' + df['vendor'].fillna('')

            # Utwórz pipeline modelu
            self.model = Pipeline([
                ('tfidf', TfidfVectorizer(ngram_range=(1, 2))),
                ('clf', MultinomialNB())
            ])

            # Trenuj model
            self.model.fit(df['features'], df['category'])

            # Zapisz model
            self.save_model()

            logger.info(f"Successfully trained model on {len(df)} expenses across {len(valid_categories)} categories")
            return True

        except Exception as e:
            logger.error(f"Error training model: {str(e)}", exc_info=True)
            return False

    def predict_category(self, transcription, vendor=None):
        """Predict category based on transcription and vendor"""
        if not self.model:
            logger.warning("No trained model available for prediction")
            return None

        try:
            # Połącz cechy
            features = transcription + ' ' + (vendor or '')

            # Przewiduj kategorię
            predicted_category = self.model.predict([features])[0]

            # Opcjonalnie możemy też pobrać prawdopodobieństwa dla wszystkich kategorii
            probabilities = self.model.predict_proba([features])[0]
            confidence = max(probabilities)

            # Zwróć przewidywanie tylko jeśli pewność jest wystarczająca
            if confidence > 0.6:  # Próg pewności
                return predicted_category
            return None

        except Exception as e:
            logger.error(f"Error predicting category: {str(e)}")
            return None

    def predict_category_with_confidence(self, transcription, vendor=None):
        """Predict category with confidence score"""
        if not self.model:
            logger.warning("No trained model available for prediction")
            return None, 0.0

        try:
            # Połącz cechy
            features = transcription + ' ' + (vendor or '')

            # Przewiduj kategorię
            predicted_category = self.model.predict([features])[0]

            # Pobierz prawdopodobieństwa dla wszystkich kategorii
            probabilities = self.model.predict_proba([features])[0]
            confidence = max(probabilities)

            # Zwróć przewidywanie i poziom pewności
            return predicted_category, confidence

        except Exception as e:
            logger.error(f"Error predicting category with confidence: {str(e)}")
            return None, 0.0

    def incremental_train(self, expense_id, confirmed_category):
        """
        Przyrostowo trenuj model na podstawie pojedynczego potwierdzonego wydatku.

        Args:
            expense_id (int): ID wydatku, którego kategorię potwierdzono
            confirmed_category (str): Potwierdzona kategoria wydatku

        Returns:
            bool: True jeśli uczenie się powiodło, False w przeciwnym wypadku
        """
        try:
            # Pobierz dane wydatku
            expense = self.db_manager.get_expense(expense_id)
            if not expense:
                logger.warning(f"Cannot incrementally train - expense ID {expense_id} not found")
                return False

            # Jeśli model nie istnieje, najpierw musimy go stworzyć
            if not self.model:
                logger.info("No existing model for incremental training, attempting to create one")
                success = self.train_model()
                if not success:
                    logger.warning("Failed to create initial model for incremental training")
                    return False

            # Przygotuj dane do uczenia
            features = expense['transcription'] + ' ' + (expense['vendor'] or '')
            category = confirmed_category

            # Sprawdź, czy mamy wystarczającą ilość danych do uczenia przyrostowego
            if not features or not category:
                logger.warning("Insufficient data for incremental training")
                return False

            # Aktualizuj model - najpierw przekształć dane za pomocą tfidf
            X_new = self.model.named_steps['tfidf'].transform([features])
            y_new = [category]

            # Sprawdź czy kategoria jest w zbiorze klas, jeśli nie, rozszerz klasy
            classes = list(self.model.named_steps['clf'].classes_)
            if category not in classes:
                classes.append(category)
                logger.info(f"Adding new category to model classes: {category}")

            # Aktualizuj klasyfikator przyrostowo
            # MultinomialNB obsługuje uczenie przyrostowe przez partial_fit
            self.model.named_steps['clf'].partial_fit(X_new, y_new, classes=classes)

            # Zapisz zaktualizowany model
            self.save_model()

            logger.info(f"Successfully updated model incrementally with expense ID {expense_id}")
            return True

        except Exception as e:
            logger.error(f"Error in incremental training: {str(e)}", exc_info=True)
            return False