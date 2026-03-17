# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /app
COPY pom.xml .
# Download dependencies first (cache layer)
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn clean package -DskipTests -B

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app

# Create non-root user
RUN addgroup -S chaos && adduser -S chaos -G chaos

COPY --from=builder /app/target/chaos-app-1.0.0.jar app.jar

RUN chown chaos:chaos app.jar
USER chaos

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
