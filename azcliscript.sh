az acr build -r gmacr1891westus https://github.com/gabrielmccoll/AzureDevopsContainerAgent.git#:ado_image -f "Dockerfile" --platform linux -t gmtest/adoagent:v1


az acr task create -t gmtest/adoagent:{{.Run.ID}} -n clitask -r gmacr1891westus \
    -c https://github.com/gabrielmccoll/AzureDevopsContainerAgent.git#:ado_image -f Dockerfile \
    --commit-trigger-enabled true --base-image-trigger-enabled false \
    --arg DOCKER_CLI_BASE_IMAGE=docker:18.03.0-ce-git