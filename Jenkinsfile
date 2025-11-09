pipeline {
    agent any
    
    environment {
        DOCKER_COMPOSE_VERSION = '2.23.0'
        PROJECT_NAME = 'aqts'
    }
    
    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm
            }
        }
        
        stage('Build') {
            steps {
                echo 'Building Docker images...'
                script {
                    sh 'docker-compose build --no-cache'
                }
            }
        }
        
        stage('Test - Unit Tests') {
            steps {
                echo 'Running unit tests...'
                script {
                    sh '''
                        cd tests
                        pip install -r requirements.txt
                        python -m pytest test_strategies.py -v
                    '''
                }
            }
        }
        
        stage('Test - Integration Tests') {
            steps {
                echo 'Running integration tests...'
                script {
                    sh '''
                        cd tests
                        python -m pytest test_integration.py -v
                    '''
                }
            }
        }
        
        stage('Code Quality Check') {
            steps {
                echo 'Running code quality checks...'
                script {
                    sh '''
                        pip install flake8
                        flake8 data-service/app.py --max-line-length=120 --ignore=E501,W503 || true
                        flake8 strategy-engine/app.py --max-line-length=120 --ignore=E501,W503 || true
                    '''
                }
            }
        }
        
        stage('Deploy - Stop Old Containers') {
            steps {
                echo 'Stopping old containers...'
                script {
                    sh 'docker-compose down || true'
                }
            }
        }
        
        stage('Deploy - Start Services') {
            steps {
                echo 'Starting services...'
                script {
                    sh 'docker-compose up -d'
                }
            }
        }
        
        stage('Health Check') {
            steps {
                echo 'Performing health checks...'
                script {
                    sleep 15
                    sh '''
                        curl -f http://localhost:5001/health || exit 1
                        curl -f http://localhost:5002/health || exit 1
                        echo "All services are healthy!"
                    '''
                }
            }
        }
    }
    
    post {
        success {
            echo 'Pipeline completed successfully! ✅'
            echo 'Services are running:'
            echo '- Data Service: http://localhost:5001'
            echo '- Strategy Engine: http://localhost:5002'
            echo '- Dashboard: http://localhost:8501'
        }
        failure {
            echo 'Pipeline failed! ❌'
            echo 'Rolling back...'
            sh 'docker-compose down || true'
        }
        always {
            echo 'Cleaning up...'
            sh 'docker system prune -f || true'
        }
    }
}
