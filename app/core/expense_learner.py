import json

import numpy as np
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
        """Train model on historical expense data and save metrics"""
        try:
            # Najpierw oceniamy model przed treningiem
            pre_metrics = None
            if self.model:
                pre_metrics = self.evaluate_model()

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

            # Po treningu oceniamy model ponownie
            post_metrics = self.evaluate_model()
            if post_metrics:
                notes = ""
                if pre_metrics:
                    accuracy_change = post_metrics['accuracy'] - pre_metrics['accuracy']
                    notes = f"Accuracy change: {accuracy_change:.4f} ({pre_metrics['accuracy']:.4f} -> {post_metrics['accuracy']:.4f})"

                self.save_metrics(post_metrics, "full", notes)

            # Zapisz model
            self.save_model()

            logger.info(f"Successfully trained model on {len(df)} expenses across {len(valid_categories)} categories")
            return True

        except Exception as e:
            logger.error(f"Error training model: {str(e)}", exc_info=True)
            return False

    def incremental_train(self, expense_id, confirmed_category):
        """
        Przyrostowo trenuj model na podstawie pojedynczego potwierdzonego wydatku i zapisz metryki.

        Args:
            expense_id (int): ID wydatku, którego kategorię potwierdzono
            confirmed_category (str): Potwierdzona kategoria wydatku

        Returns:
            bool: True jeśli uczenie się powiodło, False w przeciwnym wypadku
        """
        try:
            # Najpierw oceniamy model przed treningiem przyrostowym
            pre_metrics = None
            if self.model:
                pre_metrics = self.evaluate_model()

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

            # Oceń model po treningu przyrostowym
            post_metrics = self.evaluate_model()
            if post_metrics:
                notes = f"Incremental training for expense ID {expense_id}"
                if pre_metrics:
                    accuracy_change = post_metrics['accuracy'] - pre_metrics['accuracy']
                    notes += f", Accuracy change: {accuracy_change:.4f} ({pre_metrics['accuracy']:.4f} -> {post_metrics['accuracy']:.4f})"

                self.save_metrics(post_metrics, "incremental", notes)

            # Zapisz zaktualizowany model
            self.save_model()

            logger.info(f"Successfully updated model incrementally with expense ID {expense_id}")
            return True

        except Exception as e:
            logger.error(f"Error in incremental training: {str(e)}", exc_info=True)
            return False

    def evaluate_model(self):
        """Evaluate model using cross-validation"""
        try:
            # Pobierz dane historyczne
            expenses = self.db_manager.get_all_expenses_for_training()
            if not expenses or len(expenses) < 10:
                return None

            df = pd.DataFrame(expenses)

            # Przygotuj cechy
            category_counts = df['category'].value_counts()
            valid_categories = category_counts[category_counts >= self.min_samples_per_category].index.tolist()
            df = df[df['category'].isin(valid_categories)]
            df['features'] = df['transcription'] + ' ' + df['vendor'].fillna('')

            # Przeprowadź walidację krzyżową
            from sklearn.model_selection import cross_val_score, StratifiedKFold
            pipeline = Pipeline([
                ('tfidf', TfidfVectorizer(ngram_range=(1, 2))),
                ('clf', MultinomialNB())
            ])

            X = df['features'].values
            y = df['category'].values

            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            cv_scores = cross_val_score(pipeline, X, y, cv=cv, scoring='accuracy')

            # Utwórz macierz pomyłek
            from sklearn.model_selection import cross_val_predict
            from sklearn.metrics import confusion_matrix
            y_pred = cross_val_predict(pipeline, X, y, cv=cv)
            cm = confusion_matrix(y, y_pred, labels=valid_categories)

            # Znajdź najważniejsze cechy (nie da się bezpośrednio z CV)
            pipeline.fit(X, y)
            feature_names = pipeline.named_steps['tfidf'].get_feature_names_out()
            feature_importance = pipeline.named_steps['clf'].feature_log_prob_

            top_features = {}
            for i, category in enumerate(pipeline.named_steps['clf'].classes_):
                indices = np.argsort(feature_importance[i])[-10:]  # 10 najważniejszych
                top_features[category] = [feature_names[idx] for idx in indices]

            return {
                'accuracy': np.mean(cv_scores),
                'samples_count': len(df),
                'categories_count': len(valid_categories),
                'confusion_matrix': cm.tolist(),
                'confusion_labels': valid_categories,
                'top_features': top_features,
                'cv_scores': cv_scores.tolist()
            }
        except Exception as e:
            logger.error(f"Error evaluating model: {str(e)}", exc_info=True)
            return None

    def save_metrics(self, metrics, training_type="full", notes=""):
        """Save model metrics to database"""
        try:
            metrics_json = json.dumps({
                'confusion_matrix': metrics['confusion_matrix'],
                'confusion_labels': metrics['confusion_labels'],
                'top_features': metrics['top_features'],
                'cv_scores': metrics['cv_scores']
            })

            with self.db_manager._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO model_metrics
                        (accuracy, samples_count, categories_count, confusion_matrix, 
                         training_type, notes)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        metrics['accuracy'],
                        metrics['samples_count'],
                        metrics['categories_count'],
                        metrics_json,
                        training_type,
                        notes
                    ))
                conn.commit()
            logger.info(f"Model metrics saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving metrics: {str(e)}", exc_info=True)
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

