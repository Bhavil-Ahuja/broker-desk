# 🏠 Real Estate Broker Chat

An event-driven real estate broker chat application using Kafka, PostgreSQL, and LangChain with Ollama.

## 🏗️ Architecture

```
User Input (Streamlit UI)
    ↓
Flask API (producer.py) - Port 5001
    ↓
Kafka Topic: 'lead-events-consumer'
    ↓
Kafka Consumer (consumer.py)
    ↓
PostgreSQL (stores conversation)
    ↓
LLM Processor (llm_processor.py - Ollama Llama 3.2)
    ↓
Kafka Topic: 'broker-response'
    ↓
Streamlit UI (displays response)
```

## 📦 Components

- **Streamlit UI** (`app/ui/streamlit_app.py`): Chat interface (lead) and `app/ui/broker_dashboard.py` (broker)
- **React UI** (`client/`): Separate lead and broker dashboards with Socket.IO real-time updates (see [client/README.md](client/README.md))
- **Flask API** (`app/api/producer.py`): REST API gateway + Socket.IO
- **Kafka Consumer** (`app/api/consumer.py`): Message processor
- **LLM Processor** (`app/llm/llm_processor.py`): AI response generator
- **Database Models** (`app/models/`): SQLAlchemy models for persistence

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Ollama with Llama 3.2 model installed

### 1. Start Infrastructure

```bash
# Start Kafka, Zookeeper, PostgreSQL
docker-compose up -d

# Verify containers are running
docker-compose ps
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start Services (in separate terminals)

**Terminal 1: Flask API**
```bash
python app/api/producer.py
```

**Terminal 2: Kafka Consumer**
```bash
python app/api/consumer.py
```

**Terminal 3: Streamlit UI**
```bash
streamlit run app/ui/streamlit_app.py
```

### 4. Access the Application

- **Streamlit UI**: http://localhost:8501 (lead), broker dashboard: run `streamlit run app/ui/broker_dashboard.py`
- **React UI** (optional): `cd client && npm install && npm run dev` then http://localhost:3000 (lead), http://localhost:3000/broker (broker)
- **Kafka UI**: http://localhost:8080
- **PgAdmin**: http://localhost:5050 (admin@admin.com / admin)

## 🔧 Recent Fixes

### Chat History Persistence (FIXED)

**Problem**: Multiple responses for single question, history lost on refresh

**Solution**:
1. Created `Conversation` table to store all messages
2. Load chat history from database on page load
3. Only fetch NEW responses from Kafka (not historical ones)
4. Proper message correlation between questions and answers

## 🗃️ Database Schema

### `messages` (Legacy)
- `id`: UUID
- `message`: Text
- `user_id`: Integer
- `created_at`: DateTime (IST)

### `conversations` (New)
- `id`: UUID
- `user_id`: Integer
- `role`: 'user' or 'assistant'
- `content`: Text
- `created_at`: DateTime (IST)

## 🧪 Testing the Fix

### Reset Everything
```bash
# Stop all services
docker-compose down -v

# Restart infrastructure (this clears the database and Kafka topics)
docker-compose up -d

# Wait 10 seconds for services to be ready
sleep 10

# Restart your Python services
```

### Test Flow
1. Open Streamlit UI
2. Send message: "Looking for 2BHK in Koramangala"
3. Wait for response
4. **Refresh the page** - you should see the same conversation
5. Send another message
6. You should see ONLY ONE new response (not multiple)

## 📊 Monitoring

### View Kafka Messages
Go to http://localhost:8080 and view:
- `lead-events-consumer` topic
- `broker-response` topic

### View Database
Go to http://localhost:5050:
1. Login with admin@admin.com / admin
2. Add server: `postgres:5432` (user/password)
3. View `conversations` table

## 🛠️ Troubleshooting

### No Response Received
- Check if Ollama is running: `ollama list`
- Check consumer logs for errors
- Verify Kafka topics exist in Kafka UI

### Multiple Responses
- Stop all services
- Run `docker-compose down -v` to clear Kafka and DB
- Restart everything

### Database Connection Error
- Verify PostgreSQL is running: `docker ps | grep postgres`
- Check connection string in `app/models/__init__.py`

## 📝 API Endpoints

### POST /send
Send a message to the broker
```json
{
  "message": "Looking for 2BHK",
  "user_id": 123
}
```

### GET /history/:user_id
Get conversation history for a user
```json
{
  "history": [
    {"role": "user", "content": "Hi", "created_at": "2026-01-25T..."},
    {"role": "assistant", "content": "Hello!", "created_at": "2026-01-25T..."}
  ]
}
```

## 🎯 Future Enhancements

- [ ] State machine for lead management
- [ ] RAG pipeline for property matching
- [ ] Human-in-the-loop approval workflow
- [ ] WhatsApp integration
- [ ] MCP integration for external tools
- [ ] Multi-user authentication

## 📄 License

MIT
