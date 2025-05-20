# Expense Tracker

Expense Tracker is a comprehensive system for tracking, analyzing, and reporting personal and business expenses. The application leverages modern natural language processing and machine learning technologies to automatically categorize expenses based on voice transcriptions, significantly streamlining the process of recording daily expenses.

## 🚀 Features

### 📝 Expense Recording
- **Speech Recognition**: Record expenses through voice recordings describing the transaction - the system automatically processes the recording into text using OpenAI Whisper API
- **Automatic Categorization**: ML model automatically assigns categories to expenses based on description and historical data
- **Manual Entry**: Traditional form for manual expense entry
- **Multilingual Support**: Support for Polish and English in voice commands

### 📊 Reporting
- **Flexible Reports**: Generate reports by category, time period, and various grouping forms (day/week/month/year)
- **Visualizations**: Advanced charts and graphics showing expense trends
- **Export Formats**: PDF, Excel, and CSV for easy integration with other tools
- **Voice Commands**: Create reports through natural voice instructions

### 🤖 Integrations
- **Discord Bot**: Remote expense addition through voice messages on Discord
- **Email Notifications**: Automatic reports and confirmations sent via email
- **Machine Learning**: The system improves categorization over time, adapting to user spending patterns

## 🛠 Technologies

- **Backend**: Python 3 with Flask framework
- **Frontend**: HTML5, Bootstrap 5, JavaScript
- **Database**: MySQL
- **AI & ML**:
  - OpenAI API (GPT-3.5 and Whisper) for natural language processing and speech transcription
  - Scikit-learn for machine learning and category classification
  - SpaCy for advanced natural language processing
- **Data Visualization**: Matplotlib and Seaborn for chart generation
- **PDF**: ReportLab for generating professional PDF reports
- **Discord**: discord.py for Discord bot integration

## 🗂 Project Structure

### Key Modules
- **Transcription and Audio Analysis**:
  - `transcription.py` - converting audio recordings to text
  - `expense_extractor.py` - extracting expense details from text

- **Natural Language Processing**:
  - `nlp_category_parser.py` - detecting categories and dates from text commands
  - `category_service.py` - managing and translating categories

- **Machine Learning**:
  - `expense_learner.py` - ML model for automatic expense categorization

- **Reporting**:
  - `report_generator.py` - creating various reports and visualizations in different formats

- **Integrations**:
  - `discord_bot.py` - handling remote expense addition via Discord
  - `email_service.py` - sending notifications and reports via email

- **Data Layer**:
  - `db_manager.py` - managing all database operations

## 🚀 Deployment

The system can be deployed as:
- Web application accessible via browser
- Discord service for remote expense tracking
- Automatic email reporting system

## 🔧 Configuration

The application uses environment variables for key parameters:
- MySQL database access credentials
- OpenAI API keys
- SMTP configuration for email notifications
- Discord bot token

## 💡 Unique Machine Learning Model

The application utilizes a proprietary expense categorization model that:
- Learns from historical expenses
- Adapts to individual spending patterns
- Handles multilingual inputs
- Suggests categories with confidence measures
- Offers incremental learning (improving categorization over time)

## 📱 User Interface

Intuitive web interface with three main sections:
- Expense recording (voice or manual)
- Viewing expense history with filtering
- Generating and customizing reports

## 🔐 Security

- Secure data storage in MySQL database
- SSL encryption for email communication
- Authentication for Discord API
- Secure API key management

---

Expense Tracker Pro represents a modern approach to expense tracking, eliminating tedious manual data entry and offering advanced analysis capabilities. Through integration with AI, ML, and speech recognition technologies, the system provides a comprehensive solution for both individuals and businesses seeking an effective way to control their budget.
