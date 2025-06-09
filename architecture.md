```mermaid
[graph TB
    subgraph "Email Sources"
        A[GitHub Notifications] 
        B[GitLab Notifications]
        C[Forwarded Emails]
        D[Custom Systems]
    end
    
    subgraph "Postmark Infrastructure"
        E[Inbound Email Processing]
        F[Webhook Delivery]
    end
    
    subgraph "PR Reminder Core"
        G[FastAPI Backend]
        H[Email Parser Engine]
        I[PostgreSQL Database]
        J[Authentication Layer]
        K[Notification Queue]
    end
    
    subgraph "Frontend Dashboard"
        L[Next.js React App]
        M[Real-time Analytics]
        N[User Management]
        O[Filter Configuration]
    end
    
    subgraph "Communication Channels"
        P[Slack Integration]
        Q[Discord Webhooks]
        R[WhatsApp API]
        S[Custom Webhooks]
        T[Mobile Push]
    end
    
    subgraph "External Services"
        U[Google OAuth]
        V[Slack OAuth]
        W[GitHub API]
    end
    
    A --> E
    B --> E
    C --> E
    D --> E
    
    E --> F
    F --> G
    
    G --> H
    H --> I
    G --> J
    G --> K
    
    L --> G
    M --> I
    N --> J
    O --> H
    
    K --> P
    K --> Q
    K --> R
    K --> S
    K --> T
    
    J --> U
    J --> V
    H --> W
    
    style E fill:#ff6b35
    style F fill:#ff6b35
    style G fill:#4285f4
    style H fill:#34a853
    style P fill:#4a154b
    style L fill:#000000
    
    classDef postmark fill:#ff6b35,stroke:#fff,stroke-width:2px,color:#fff
    classDef backend fill:#4285f4,stroke:#fff,stroke-width:2px,color:#fff
    classDef parser fill:#34a853,stroke:#fff,stroke-width:2px,color:#fff
    classDef slack fill:#4a154b,stroke:#fff,stroke-width:2px,color:#fff
    classDef frontend fill:#000000,stroke:#fff,stroke-width:2px,color:#fff]