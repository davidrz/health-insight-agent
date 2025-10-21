# Health Insight Agent - Diagrama de Arquitectura

## Arquitectura General del Sistema

```mermaid
graph TB
    %% External Services
    subgraph "AWS Services"
        Bedrock[AWS Bedrock<br/>LLM Services]
        SageMaker[AWS SageMaker<br/>ML Models]
    end
    
    %% Application Layers
    subgraph "Health Insight Agent System"
        %% API Layer (Future)
        subgraph "API Layer (Task 6)"
            API[FastAPI<br/>REST Endpoints]
            WebSocket[WebSocket<br/>Real-time Updates]
        end
        
        %% Agents Layer
        subgraph "Agents Layer"
            Orchestrator[Agent Orchestrator<br/>Multi-agent coordination]
            MCP[MCP Server<br/>Agent communication]
            
            subgraph "AI Agents"
                BedrockAgent[Bedrock Agent<br/>NL Insights]
                RiskAgent[SageMaker Risk Agent<br/>Risk Prediction]
                AnomalyAgent[SageMaker Anomaly Agent<br/>Anomaly Detection]
            end
        end
        
        %% Domain Layer
        subgraph "Domain Layer"
            Entities[Domain Entities<br/>HealthData, VitalSigns, etc.]
            ValueObjects[Value Objects<br/>InsightReport, RiskAssessment]
            Services[Domain Services<br/>Business Logic]
        end
        
        %% Infrastructure Layer
        subgraph "Infrastructure Layer"
            BedrockClient[Bedrock Client<br/>AWS Integration]
            SageMakerClient[SageMaker Client<br/>ML Integration]
            Database[PostgreSQL<br/>Data Persistence]
            Cache[Redis Cache<br/>Performance]
            Repositories[Data Repositories<br/>Data Access]
        end
    end
    
    %% External Database
    PostgresDB[(PostgreSQL<br/>Database)]
    RedisCache[(Redis<br/>Cache)]
    
    %% Connections
    API --> Orchestrator
    WebSocket --> Orchestrator
    
    Orchestrator --> MCP
    MCP --> BedrockAgent
    MCP --> RiskAgent
    MCP --> AnomalyAgent
    
    BedrockAgent --> BedrockClient
    RiskAgent --> SageMakerClient
    AnomalyAgent --> SageMakerClient
    
    BedrockClient --> Bedrock
    SageMakerClient --> SageMaker
    
    Orchestrator --> Services
    Services --> Entities
    Services --> ValueObjects
    
    Repositories --> Database
    Cache --> RedisCache
    Database --> PostgresDB
    
    %% Styling
    classDef aws fill:#ff9900,stroke:#232f3e,stroke-width:2px,color:#fff
    classDef agent fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
    classDef domain fill:#2196F3,stroke:#1565C0,stroke-width:2px,color:#fff
    classDef infra fill:#9C27B0,stroke:#6A1B9A,stroke-width:2px,color:#fff
    classDef api fill:#FF5722,stroke:#D84315,stroke-width:2px,color:#fff
    classDef db fill:#607D8B,stroke:#37474F,stroke-width:2px,color:#fff
    
    class Bedrock,SageMaker aws
    class Orchestrator,MCP,BedrockAgent,RiskAgent,AnomalyAgent agent
    class Entities,ValueObjects,Services domain
    class BedrockClient,SageMakerClient,Database,Cache,Repositories infra
    class API,WebSocket api
    class PostgresDB,RedisCache db
```

## Flujo de Comunicación Detallado

```mermaid
sequenceDiagram
    participant Client as Cliente/API
    participant Orch as Agent Orchestrator
    participant MCP as MCP Server
    participant BA as Bedrock Agent
    participant RA as Risk Agent
    participant AA as Anomaly Agent
    participant BC as Bedrock Client
    participant SC as SageMaker Client
    participant AWS as AWS Services
    
    Client->>Orch: analyze_health_data(health_data)
    
    Note over Orch: Iniciar workflow de análisis
    
    %% Risk Prediction
    Orch->>MCP: execute_agent_task(RiskTask)
    MCP->>RA: execute_task(task)
    RA->>SC: predict_risk_factors(metrics)
    SC->>AWS: invoke_endpoint(sagemaker)
    AWS-->>SC: risk_assessment
    SC-->>RA: RiskAssessment
    RA-->>MCP: AgentResponse(risk_data)
    MCP-->>Orch: risk_results
    
    %% Natural Language Insights
    Orch->>MCP: execute_agent_task(BedrockTask)
    MCP->>BA: execute_task(task)
    BA->>BC: generate_insights(prompt, context)
    BC->>AWS: invoke_model(bedrock)
    AWS-->>BC: insights_text
    BC-->>BA: insights
    BA-->>MCP: AgentResponse(insights_data)
    MCP-->>Orch: insights_results
    
    %% Anomaly Detection (Optional)
    opt include_anomaly_detection
        Orch->>MCP: execute_agent_task(AnomalyTask)
        MCP->>AA: execute_task(task)
        AA->>SC: detect_anomalies(time_series)
        SC->>AWS: invoke_endpoint(sagemaker)
        AWS-->>SC: anomaly_report
        SC-->>AA: AnomalyReport
        AA-->>MCP: AgentResponse(anomaly_data)
        MCP-->>Orch: anomaly_results
    end
    
    Note over Orch: Combinar resultados y generar reporte
    
    Orch-->>Client: InsightReport(comprehensive_analysis)
```

## Estructura de Directorios Actual

```
backend/
├── app/
│   ├── agents/                    # Capa de Agentes (Task 5 ✅)
│   │   ├── __init__.py           # Exports principales
│   │   ├── base.py               # Interfaces base y registry
│   │   ├── mcp_server.py         # Servidor MCP
│   │   ├── bedrock_agent.py      # Agente Bedrock
│   │   ├── sagemaker_agent.py    # Agentes SageMaker
│   │   └── orchestrator.py       # Orquestador principal
│   │
│   ├── domain/                   # Capa de Dominio (Tasks 1-2 ✅)
│   │   ├── entities.py           # Entidades de negocio
│   │   ├── value_objects.py      # Objetos de valor
│   │   └── services.py           # Servicios de dominio
│   │
│   ├── infra/                    # Capa de Infraestructura (Tasks 3-4 ✅)
│   │   ├── database.py           # Configuración DB
│   │   ├── models.py             # Modelos SQLAlchemy
│   │   ├── repositories.py       # Repositorios de datos
│   │   ├── cache.py              # Cliente Redis
│   │   ├── aws_bedrock.py        # Cliente Bedrock
│   │   └── aws_sagemaker.py      # Cliente SageMaker
│   │
│   └── core/                     # Configuración central
│       └── config.py             # Settings de la aplicación
│
├── alembic/                      # Migraciones de DB
└── tests/                        # Tests del sistema
```

## Dependencias Entre Componentes

### 1. **Agents Layer** (Nivel más alto)
- **Orchestrator** → MCP Server → Individual Agents
- **Agents** → Infrastructure Clients → AWS Services
- **Agents** → Domain Services → Domain Entities

### 2. **Domain Layer** (Lógica de negocio)
- **Services** → Entities + Value Objects
- **Entities** ← Value Objects (composición)

### 3. **Infrastructure Layer** (Servicios externos)
- **AWS Clients** → AWS Services (Bedrock, SageMaker)
- **Repositories** → Database (PostgreSQL)
- **Cache** → Redis

## Patrones de Diseño Implementados

### 1. **Agent Pattern**
- Agentes autónomos especializados
- Comunicación a través de MCP Server
- Registro y descubrimiento de agentes

### 2. **Orchestrator Pattern**
- Coordinación de múltiples agentes
- Workflow de análisis configurable
- Síntesis de resultados

### 3. **Circuit Breaker Pattern**
- Resilencia en clientes AWS
- Manejo de fallos temporales
- Recuperación automática

### 4. **Repository Pattern**
- Abstracción de acceso a datos
- Separación de persistencia y dominio

### 5. **Domain-Driven Design (DDD)**
- Entidades y objetos de valor
- Servicios de dominio
- Separación clara de capas

## Estado de Implementación

| Componente | Estado | Tarea |
|------------|--------|-------|
| Domain Entities | ✅ Completo | Task 1 |
| Domain Services | ✅ Completo | Task 2 |
| Database & Models | ✅ Completo | Task 3 |
| AWS Clients | ✅ Completo | Task 4 |
| Agent Orchestration | ✅ Completo | Task 5 |
| API Layer | 🔄 Pendiente | Task 6 |
| Integration Tests | 🔄 Pendiente | Task 7 |

## Próximos Pasos (Task 6)

La siguiente tarea implementará la **API Layer** que incluirá:

1. **FastAPI Application** - Endpoints REST
2. **WebSocket Support** - Actualizaciones en tiempo real
3. **API Routes** - Endpoints para análisis de salud
4. **Request/Response Models** - Validación de datos
5. **Error Handling** - Manejo de errores HTTP
6. **Authentication** - Seguridad básica

Esta capa se conectará directamente con el **Agent Orchestrator** para proporcionar una interfaz externa al sistema.