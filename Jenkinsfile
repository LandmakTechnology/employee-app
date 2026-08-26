pipeline {
    agent any

    environment {
        DOCKERHUB_BACKEND  = 'flezobaba/employee-backend'
        DOCKERHUB_FRONTEND = 'flezobaba/employee-frontend'
        IMAGE_TAG          = "build-${BUILD_NUMBER}"
    }

    stages {

        stage('Test') {
            steps {
                sh '''
                    pip install -r backend/requirements.txt
                    cd backend
                    DATABASE_URL=sqlite:///test.db pytest -v
                '''
            }
        }

        stage('Build & Push') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'dockerhub-credentials',
                    usernameVariable: 'DOCKER_USER',
                    passwordVariable: 'DOCKER_PASS'
                )]) {
                    sh '''
                        echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin

                        docker build -t $DOCKERHUB_BACKEND:$IMAGE_TAG backend/
                        docker push $DOCKERHUB_BACKEND:$IMAGE_TAG
                        docker tag $DOCKERHUB_BACKEND:$IMAGE_TAG $DOCKERHUB_BACKEND:latest
                        docker push $DOCKERHUB_BACKEND:latest

                        docker build -t $DOCKERHUB_FRONTEND:$IMAGE_TAG frontend/
                        docker push $DOCKERHUB_FRONTEND:$IMAGE_TAG
                        docker tag $DOCKERHUB_FRONTEND:$IMAGE_TAG $DOCKERHUB_FRONTEND:latest
                        docker push $DOCKERHUB_FRONTEND:latest
                    '''
                }
            }
        }

        stage('Deploy') {
            steps {
                withCredentials([
                    sshUserPrivateKey(
                        credentialsId: 'ec2-ssh-key',
                        keyFileVariable: 'SSH_KEY',
                        usernameVariable: 'SSH_USER'
                    ),
                    string(credentialsId: 'ec2-host', variable: 'EC2_HOST'),
                    string(credentialsId: 'database-url', variable: 'DATABASE_URL')
                ]) {
                    sh '''
                        ssh -o StrictHostKeyChecking=no -i $SSH_KEY $SSH_USER@$EC2_HOST "
                            docker pull $DOCKERHUB_BACKEND:$IMAGE_TAG
                            docker pull $DOCKERHUB_FRONTEND:$IMAGE_TAG

                            docker network create employee-network 2>/dev/null || true

                            docker rm -f backend frontend 2>/dev/null || true

                            docker run -d --name backend --restart unless-stopped \
                              --network employee-network \
                              -p 5000:5000 \
                              -e DATABASE_URL=$DATABASE_URL \
                              $DOCKERHUB_BACKEND:$IMAGE_TAG

                            docker run -d --name frontend --restart unless-stopped \
                              --network employee-network \
                              -p 80:80 \
                              $DOCKERHUB_FRONTEND:$IMAGE_TAG
                        "
                    '''
                }
            }
        }
    }

    post {
        success { echo "Deployed build-${BUILD_NUMBER} to EC2 successfully" }
        failure { echo "Pipeline failed — check logs above" }
    }
}
