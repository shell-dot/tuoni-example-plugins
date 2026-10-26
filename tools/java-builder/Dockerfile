FROM eclipse-temurin:25-jdk
ENV GRADLE_USER_HOME=/opt/gradle-home
WORKDIR /opt/dependency-project
COPY gradlew build.gradle.kts settings.gradle.kts ./
COPY gradle/ gradle/

# Keep the resolved files and repository metadata in the image itself.
RUN sh ./gradlew resolveDependencies --no-daemon \
    && rm -rf .gradle "$GRADLE_USER_HOME/daemon" \
    && find "$GRADLE_USER_HOME" -type f \( -name '*.lock' -o -name '*.lck' -o -name gc.properties \) -delete \
    && chmod -R a+rX "$GRADLE_USER_HOME"

WORKDIR /build
