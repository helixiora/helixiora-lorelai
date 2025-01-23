#!/bin/bash

# this script deploys containers from github (latest by default) to an ECS cluster
# it expects the following:

# - a docker image name for the worker and web containers (defaults to ghcr.io/helixiora/helixiora-lorelai/web or /worker)
# - a docker image tag

# - an ECS cluster name where 4 services are running:
# helixiora-*-ecs-service-frontend
# helixiora-*-ecs-service-worker-question
# helixiora-*-ecs-service-worker-default
# helixiora-*-ecs-service-worker-indexer

# it will deploy the latest image from github to the cluster
# web container will be deployed to the frontend service
# worker containers will be deployed to the worker-question, worker-default and worker-indexer services

# Exit on any error
set -e

# Colors and formatting
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Unicode characters
CHECK="✓"
CROSS="✗"
ARROW="→"
INFO="ℹ"
WARN="⚠"

# Logging functions
log_info() {
    echo -e "${BLUE}${INFO} $1${NC}"
}

log_success() {
    echo -e "${GREEN}${CHECK} $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}${WARN} $1${NC}"
}

log_error() {
    echo -e "${RED}${CROSS} $1${NC}"
    exit 1
}

log_dry_run() {
    echo -e "${YELLOW}${ARROW} [DRY RUN] $1${NC}"
}

log_step() {
    echo -e "\n${BOLD}${BLUE}${ARROW} $1${NC}"
}

# Default values and cache
IMAGE_TAG="latest"
DEFAULT_WEB_IMAGE="ghcr.io/helixiora/helixiora-lorelai/web"
DEFAULT_WORKER_IMAGE="ghcr.io/helixiora/helixiora-lorelai/worker"
DRY_RUN=true
WEB_SHA=""
WORKER_SHA=""

# Check for required GITHUB_TOKEN
if [ -z "$GITHUB_TOKEN" ]; then
    log_error "GITHUB_TOKEN environment variable is required but not set"
fi

print_usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -i, --image <name>     Docker image name (defaults to ghcr.io/helixiora/helixiora-lorelai/web for frontend, /worker for workers)"
    echo "  -t, --tag <tag>        Docker image tag (default: latest)"
    echo "  -c, --cluster <name>   ECS cluster name (auto-detected if only one exists)"
    echo "  -d, --deploy           Disable dry-run mode and actually deploy (default: dry-run enabled)"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Environment variables:"
    echo "  GITHUB_TOKEN          Required: GitHub token for accessing container registry"
}

# Parse command line arguments
while [ $# -gt 0 ]; do
    case "$1" in
        -i|--image)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -c|--cluster)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        -d|--deploy)
            DRY_RUN=false
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# Show deploy mode status early
if [ "$DRY_RUN" = true ]; then
    log_step "DRY RUN MODE"
    log_warning "This is a dry run - NO CHANGES WILL BE MADE TO ECS"
    log_warning "Use -d or --deploy to actually deploy changes"
    echo ""
else
    log_warning "Deploy mode enabled - changes will be applied"
fi

# Validate required parameters
if [ -z "$CLUSTER_NAME" ]; then
    log_step "Detecting ECS cluster"
    CLUSTERS=$(aws ecs list-clusters --output json | jq -r '.clusterArns[]')
    CLUSTER_COUNT=$(echo "$CLUSTERS" | wc -l)

    if [ -z "$CLUSTERS" ]; then
        log_error "No clusters found. Please specify a cluster name with -c/--cluster"
        print_usage
        exit 1
    elif [ "$CLUSTER_COUNT" -eq 1 ]; then
        CLUSTER_NAME=$(echo "$CLUSTERS" | sed 's/.*cluster\///')
        log_success "Found single cluster: $CLUSTER_NAME"
    else
        log_error "Multiple clusters found. Please specify one with -c/--cluster\nAvailable clusters:\n$(echo "$CLUSTERS" | sed 's/.*cluster\///' | sed 's/^/  - /')"
    fi
fi

# Extract the slug from cluster name (everything before '-ecs-cluster')
CLUSTER_SLUG=$(echo "$CLUSTER_NAME" | sed 's/-ecs-cluster//')
log_info "Using slug: $CLUSTER_SLUG for service names"

# Function to check GitHub Container Registry
check_github_container() {
    local image_to_use="$1"
    local image_tag="$2"
    local full_package_name=$(echo "$image_to_use" | sed 's|ghcr.io/helixiora/helixiora-lorelai/||')

    # Check if we already looked up this image
    if [ "$full_package_name" = "web" ] && [ -n "$WEB_SHA" ]; then
        echo "$WEB_SHA"
        return 0
    elif [ "$full_package_name" = "worker" ] && [ -n "$WORKER_SHA" ]; then
        echo "$WORKER_SHA"
        return 0
    fi

    if [ -n "$GITHUB_TOKEN" ]; then
        # First get the list of versions
        GITHUB_RESPONSE=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
            -H "Accept: application/vnd.github.v3+json" \
            "https://api.github.com/orgs/helixiora/packages/container/helixiora-lorelai%2F${full_package_name}/versions")

        if [ "$(echo "$GITHUB_RESPONSE" | jq -r 'type')" = "array" ]; then
            # Get the version ID for the matching tag
            VERSION_ID=$(echo "$GITHUB_RESPONSE" | jq -r --arg TAG "$image_tag" \
                '[.[] | select(.metadata.container.tags | contains([$TAG]))] | first | .id // empty')

            if [ -n "$VERSION_ID" ]; then
                # Get the specific version details which includes the manifest
                VERSION_DETAILS=$(curl -s -H "Authorization: Bearer $GITHUB_TOKEN" \
                    -H "Accept: application/vnd.github.v3+json" \
                    "https://api.github.com/orgs/helixiora/packages/container/helixiora-lorelai%2F${full_package_name}/versions/${VERSION_ID}")

                # Extract the SHA from the name field (which contains the SHA256 digest)
                CURRENT_SHA=$(echo "$VERSION_DETAILS" | jq -r '.name // empty' | sed 's/^sha256://')

                if [ -n "$CURRENT_SHA" ]; then
                    # Cache the result
                    if [ "$full_package_name" = "web" ]; then
                        WEB_SHA="$CURRENT_SHA"
                    else
                        WORKER_SHA="$CURRENT_SHA"
                    fi
                    echo "$CURRENT_SHA"
                    return 0
                fi
            fi

            # If we get here, we couldn't find the SHA
            if echo "$GITHUB_RESPONSE" | jq -e '.[].metadata.container.tags' >/dev/null; then
                log_warning "Available tags for $full_package_name:"
                echo "$GITHUB_RESPONSE" | jq -r '.[].metadata.container.tags[]' | sort -u | sed 's/^/  - /'
            fi
        else
            log_warning "Could not find image $full_package_name:$image_tag in GitHub Container Registry"
            log_warning "GitHub API Response:"
            echo "$GITHUB_RESPONSE" | jq -r '.message // "No error message"'
        fi
    else
        log_warning "GITHUB_TOKEN not set, cannot verify image in GitHub Container Registry"
    fi

    # Cache the unknown result
    if [ "$full_package_name" = "web" ]; then
        WEB_SHA="unknown"
    else
        WORKER_SHA="unknown"
    fi
    echo "unknown"
}

# Add a variable to track if any changes were made or would be made
CHANGES_DETECTED=false

# Function to extract SHA from image tag
extract_sha_from_image() {
    local service_name="$1"
    local cluster_name="$2"

    # Get the running task ARN for this service
    local task_arn=$(aws ecs list-tasks \
        --cluster "$cluster_name" \
        --service-name "$service_name" \
        --desired-status RUNNING \
        --query 'taskArns[0]' \
        --output text \
        --no-cli-pager)

    if [ "$task_arn" = "None" ] || [ -z "$task_arn" ]; then
        log_warning "No running tasks found for service $service_name"
        echo "unknown"
        return
    fi

    # Get the task details including container image digest
    local task_details=$(aws ecs describe-tasks \
        --cluster "$cluster_name" \
        --tasks "$task_arn" \
        --query 'tasks[0].containers[0].imageDigest' \
        --output text \
        --no-cli-pager)

    if [ "$task_details" = "None" ] || [ -z "$task_details" ]; then
        log_warning "Could not get image digest for task $task_arn"
        echo "unknown"
        return
    fi

    # Extract just the SHA part from the digest
    echo "$task_details" | sed 's/^sha256://'
}

# Function to update ECS service
update_service() {
    local service_name="$1"
    local task_family="$2"
    local is_worker="$3"
    local changes_needed=false

    # Determine which image to use
    local image_to_use
    if [ "$is_worker" = true ]; then
        image_to_use=${IMAGE_NAME:-$DEFAULT_WORKER_IMAGE}
    else
        image_to_use=${IMAGE_NAME:-$DEFAULT_WEB_IMAGE}
    fi

    log_step "Updating service: $service_name"
    log_info "Using image: $image_to_use:$IMAGE_TAG"

    # Get current task definition
    TASK_DEF=$(aws ecs describe-task-definition --task-definition "$task_family" --query 'taskDefinition' --output json --no-cli-pager)

    # Get current image from task definition and SHA from running container
    CURRENT_IMAGE=$(echo "$TASK_DEF" | jq -r '.containerDefinitions[0].image')
    CURRENT_SHA=$(extract_sha_from_image "$service_name" "$CLUSTER_NAME")
    log_info "Current ECS image: $CURRENT_IMAGE"
    log_info "Current ECS SHA:   $CURRENT_SHA"

    # If we're deploying the same image:tag, check if it's actually different
    if [ "$CURRENT_IMAGE" = "$image_to_use:$IMAGE_TAG" ]; then
        log_warning "Same image:tag detected, checking for updates..."

        GITHUB_SHA=$(check_github_container "$image_to_use" "$IMAGE_TAG")
        log_info "GitHub SHA:        $GITHUB_SHA"

        if [ "$GITHUB_SHA" != "unknown" ]; then
            if [ "$CURRENT_SHA" != "unknown" ] && [ "$CURRENT_SHA" = "$GITHUB_SHA" ]; then
                log_success "Service $service_name is up to date"
                return 0
            fi
            changes_needed=true
        fi
    else
        log_info "Different image detected:"
        log_info "  Current: $CURRENT_IMAGE"
        log_info "  New:     $image_to_use:$IMAGE_TAG"
        GITHUB_SHA=$(check_github_container "$image_to_use" "$IMAGE_TAG")
        log_info "GitHub SHA:        $GITHUB_SHA"
        changes_needed=true
    fi

    if [ "$changes_needed" = true ]; then
        CHANGES_DETECTED=true

        # Create new task definition
        NEW_TASK_DEF=$(echo "$TASK_DEF" | jq --arg IMAGE "$image_to_use:$IMAGE_TAG" \
            '.containerDefinitions[0].image = $IMAGE | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)')

        # Show what's changing
        if [ "$DRY_RUN" = true ]; then
            log_dry_run "Would update task definition with these changes:"
            diff_json=$(echo "$TASK_DEF" | jq --arg IMAGE "$image_to_use:$IMAGE_TAG" \
                '{image: {old: .containerDefinitions[0].image, new: $IMAGE}}')
            echo "$diff_json" | jq '.'
            log_dry_run "Would register new task definition with container image: $image_to_use:$IMAGE_TAG"
            log_dry_run "Would update service $service_name with new task definition"
        else
            log_info "Updating task definition with these changes:"
            diff_json=$(echo "$TASK_DEF" | jq --arg IMAGE "$image_to_use:$IMAGE_TAG" \
                '{image: {old: .containerDefinitions[0].image, new: $IMAGE}}')
            echo "$diff_json" | jq '.'

            # Register new task definition
            log_info "Registering new task definition..."
            NEW_TASK_DEF_ARN=$(aws ecs register-task-definition \
                --cli-input-json "$NEW_TASK_DEF" \
                --query 'taskDefinition.taskDefinitionArn' \
                --output text \
                --no-cli-pager)

            # Update service with new task definition
            log_info "Updating service..."
            aws ecs update-service \
                --cluster "$CLUSTER_NAME" \
                --service "$service_name" \
                --task-definition "$NEW_TASK_DEF_ARN" \
                --force-new-deployment \
                --query 'service.[serviceArn,serviceName]' \
                --output text \
                --no-cli-pager > /dev/null

            log_success "Service $service_name updated successfully"
        fi
    fi
}

# Update all services
log_step "Starting deployment to cluster $CLUSTER_NAME"
if [ "$DRY_RUN" = true ]; then
    log_warning "Running in dry-run mode. No changes will be made."
fi

# check if the cluster exists
if aws ecs describe-clusters --clusters "$CLUSTER_NAME" --output json > /dev/null 2>&1; then
    log_success "Cluster $CLUSTER_NAME exists"
else
    log_error "Cluster $CLUSTER_NAME does not exist"
fi

# Get services instead of tasks since we want to check running services
log_step "Checking services"
SERVICES=$(aws ecs list-services --cluster "$CLUSTER_NAME" --output json | jq -r '.serviceArns[]')
log_info "Found services in cluster $CLUSTER_NAME:"
echo "$SERVICES" | sed "s|.*service/${CLUSTER_NAME}/||" | sed 's/^/  - /'

if [ -z "$SERVICES" ]; then
    log_error "No services found in cluster $CLUSTER_NAME"
fi

# Count services (using line count since jq outputs one per line)
SERVICE_COUNT=$(echo "$SERVICES" | wc -l)
if [ "$SERVICE_COUNT" -ne 4 ]; then
    log_error "Expected 4 services in cluster $CLUSTER_NAME, found $SERVICE_COUNT"
fi

# Check for required services
required_services=(
    "${CLUSTER_SLUG}-ecs-service-frontend"
    "${CLUSTER_SLUG}-ecs-service-worker-question"
    "${CLUSTER_SLUG}-ecs-service-worker-default"
    "${CLUSTER_SLUG}-ecs-service-worker-indexer"
)

log_info "Validating required services..."
for service in "${required_services[@]}"; do
    # Extract just the service name from the full ARN for comparison
    if ! echo "$SERVICES" | sed "s|.*service/${CLUSTER_NAME}/||" | grep -q "$service"; then
        log_error "Service $service not found in cluster $CLUSTER_NAME"
    fi
    log_info "Found service: $service"
done
log_success "All required services found"

# Update frontend service
update_service "${CLUSTER_SLUG}-ecs-service-frontend" "${CLUSTER_SLUG}-task-frontend" false

# Update worker services
update_service "${CLUSTER_SLUG}-ecs-service-worker-question" "${CLUSTER_SLUG}-task-worker-question" true
update_service "${CLUSTER_SLUG}-ecs-service-worker-default" "${CLUSTER_SLUG}-task-worker-default" true
update_service "${CLUSTER_SLUG}-ecs-service-worker-indexer" "${CLUSTER_SLUG}-task-worker-indexer" true

# Final status message
if [ "$DRY_RUN" = true ]; then
    log_step "DRY RUN COMPLETED"
    if [ "$CHANGES_DETECTED" = true ]; then
        log_warning "This was a dry run - NO CHANGES WERE MADE TO ECS"
        log_warning "Use -d or --deploy to actually deploy the changes above"
    else
        log_success "No changes needed - all services are up to date"
        log_info "No action required"
    fi
else
    if [ "$CHANGES_DETECTED" = true ]; then
        log_success "Deployment completed successfully!"
    else
        log_success "No changes needed - all services are up to date"
        log_info "No action taken"
    fi
fi
