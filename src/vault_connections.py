#!/usr/bin/env python3
"""Command-line interface for testing RAG Config Manager vault operations."""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger
from rag_config_manager.vault import VaultClient, ConnectionManager
from rag_config_manager.models import ProviderType, Environment
from rag_config_manager.exceptions import RAGConfigManagerError


# Configure loguru
logger.remove()  # Remove default handler
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
)


class VaultConnectionCLI:
    """CLI for managing vault connections."""

    def __init__(self):
        """Initialize CLI."""
        self.current_user: str = ""
        self.vault_client: VaultClient
        self.connection_manager: ConnectionManager
        self._initialize_vault()

    def _initialize_vault(self):
        """Initialize Vault client and connection manager."""
        try:
            vault_url = os.getenv("VAULT_ADDR", "http://localhost:8200")
            vault_token = os.getenv("VAULT_TOKEN")

            self.vault_client = VaultClient(vault_url=vault_url, token=vault_token)
            self.connection_manager = ConnectionManager(self.vault_client)

            if not self.vault_client.is_vault_available():
                logger.error("Vault is not available. Please ensure Vault is running.")
                sys.exit(1)

            logger.success("Connected to Vault successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Vault: {e}")
            sys.exit(1)

    def _select_user(self):
        """Prompt user to select or create a user ID."""
        print("\n" + "=" * 50)
        print("USER SELECTION")
        print("=" * 50)
        print("Select a user ID to work with:")
        print("1. user1")
        print("2. user2")
        print("3. admin")
        print("4. Enter custom user ID")

        while True:
            choice = input("\nSelect option (1-4): ").strip()

            if choice == "1":
                self.current_user = "user1"
                break
            elif choice == "2":
                self.current_user = "user2"
                break
            elif choice == "3":
                self.current_user = "admin"
                break
            elif choice == "4":
                custom_user = input("Enter custom user ID: ").strip()
                if custom_user:
                    self.current_user = custom_user
                    break
                print("User ID cannot be empty")
            else:
                print("Invalid option. Please try again.")

        logger.info(f"Selected user: {self.current_user}")

    def create_azure_openai_connection(self):
        """Create Azure OpenAI connection interactively."""
        if not self.current_user:
            self._select_user()

        # Ensure user is selected (for type checking)
        if not self.current_user:
            print("User selection is required")
            return

        print(f"\nCREATING AZURE OPENAI CONNECTION for {self.current_user}")
        print("=" * 60)

        try:
            # Get connection details
            name = input("Connection Name: ").strip()
            if not name:
                print("Connection name is required")
                return

            endpoint = input("Azure OpenAI Endpoint: ").strip()
            api_key = input("Azure OpenAI API Key: ").strip()
            deployment_name = input("Deployment Name: ").strip()
            api_version = (
                input("API Version (default: 2025-01-01-preview): ").strip()
                or "2025-01-01-preview"
            )

            if not all([endpoint, api_key, deployment_name]):
                print("All connection fields are required")
                return

            # Get metadata
            description = (
                input("Description (optional): ").strip()
                or f"Azure OpenAI connection - {name}"
            )

            # Environment selection
            print("\nSelect Environment:")
            print("1. Development")
            print("2. Staging")
            print("3. Production")
            print("4. Testing")

            env_choice = input("Select environment (1-4, default: 1): ").strip() or "1"
            env_map = {
                "1": Environment.DEVELOPMENT,
                "2": Environment.STAGING,
                "3": Environment.PRODUCTION,
                "4": Environment.TESTING,
            }
            environment = env_map.get(env_choice, Environment.DEVELOPMENT)

            # Tags
            tags_input = input("Tags (comma-separated, optional): ").strip()
            tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else []

            # Is default
            is_default = (
                input("Set as default connection? (y/n, default: n): ").strip().lower()
                == "y"
            )

            # Create connection data
            connection_data = {
                "endpoint": endpoint,
                "api_key": api_key,
                "deployment_name": deployment_name,
                "api_version": api_version,
            }

            # Create connection
            connection_id = self.connection_manager.create_connection(
                user_id=self.current_user,
                name=name,
                provider=ProviderType.AZURE_OPENAI,
                connection_data=connection_data,
                description=description,
                environment=environment,
                tags=tags,
                is_default=is_default,
            )

            logger.success("Successfully created Azure OpenAI connection!")
            self._display_connection_summary(
                connection_id, name, environment.value, tags
            )

        except RAGConfigManagerError as e:
            logger.error(f"Failed to create Azure OpenAI connection: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def create_aws_connection(self):
        """Create AWS connection interactively."""
        if not self.current_user:
            self._select_user()

        # Ensure user is selected (for type checking)
        if not self.current_user:
            print("User selection is required")
            return

        print(f"\nCREATING AWS CONNECTION for {self.current_user}")
        print("=" * 60)

        try:
            # Get connection details
            name = input("Connection Name: ").strip()
            if not name:
                print("Connection name is required")
                return

            region = input("AWS Region (default: us-east-1): ").strip() or "us-east-1"
            access_key_id = input("AWS Access Key ID: ").strip()
            secret_access_key = input("AWS Secret Access Key: ").strip()
            session_token = input("AWS Session Token (optional): ").strip() or None

            if not all([region, access_key_id, secret_access_key]):
                print("Region, Access Key ID, and Secret Access Key are required")
                return

            # Get metadata
            description = (
                input("Description (optional): ").strip() or f"AWS connection - {name}"
            )

            # Environment selection
            print("\nSelect Environment:")
            print("1. Development")
            print("2. Staging")
            print("3. Production")
            print("4. Testing")

            env_choice = input("Select environment (1-4, default: 1): ").strip() or "1"
            env_map = {
                "1": Environment.DEVELOPMENT,
                "2": Environment.STAGING,
                "3": Environment.PRODUCTION,
                "4": Environment.TESTING,
            }
            environment = env_map.get(env_choice, Environment.DEVELOPMENT)

            # Tags
            tags_input = input("Tags (comma-separated, optional): ").strip()
            tags = [tag.strip() for tag in tags_input.split(",")] if tags_input else []

            # Is default
            is_default = (
                input("Set as default connection? (y/n, default: n): ").strip().lower()
                == "y"
            )

            # Create connection data
            connection_data = {
                "region": region,
                "access_key_id": access_key_id,
                "secret_access_key": secret_access_key,
            }
            if session_token:
                connection_data["session_token"] = session_token

            # Create connection
            connection_id = self.connection_manager.create_connection(
                user_id=self.current_user,
                name=name,
                provider=ProviderType.AWS_BEDROCK,
                connection_data=connection_data,
                description=description,
                environment=environment,
                tags=tags,
                is_default=is_default,
            )

            logger.success("Successfully created AWS connection!")
            self._display_connection_summary(
                connection_id, name, environment.value, tags
            )

        except RAGConfigManagerError as e:
            logger.error(f"Failed to create AWS connection: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    def list_connections(self):
        """List all connections for current user."""
        if not self.current_user:
            self._select_user()

        # Ensure user is selected (for type checking)
        if not self.current_user:
            print("User selection is required")
            return

        print(f"\nLISTING CONNECTIONS for {self.current_user}")
        print("=" * 60)

        try:
            # List all connections
            connections = self.connection_manager.list_user_connections(
                self.current_user
            )

            if not connections:
                print("No connections found.")
                return

            print(f"Found {len(connections)} connections:")
            print("-" * 100)
            print(
                f"{'ID':<12} {'Name':<20} {'Provider':<15} {'Environment':<12} {'Created':<12}"
            )
            print("-" * 100)

            for conn in connections:
                print(
                    f"{conn.metadata.id:<12} {conn.metadata.name:<20} {conn.metadata.provider.value:<15} {conn.metadata.environment.value:<12} {conn.metadata.created_at.strftime('%Y-%m-%d'):<12}"
                )

        except Exception as e:
            logger.error(f"Error listing connections: {e}")

    def get_connection_details(self):
        """Get detailed information about a specific connection."""
        if not self.current_user:
            self._select_user()

        # Ensure user is selected (for type checking)
        if not self.current_user:
            print("User selection is required")
            return

        print(f"\nGET CONNECTION DETAILS for {self.current_user}")
        print("=" * 60)

        try:
            connection_id = input("Enter Connection ID: ").strip()
            if not connection_id:
                print("Connection ID is required")
                return

            connection = self.connection_manager.get_connection(
                self.current_user, connection_id
            )

            if not connection:
                print(f"Connection '{connection_id}' not found")
                return

            # Display connection details
            print("\nConnection Details")
            print("-" * 50)
            print(f"ID: {connection.metadata.id}")
            print(f"Name: {connection.metadata.name}")
            print(f"Description: {connection.metadata.description}")
            print(f"Provider: {connection.metadata.provider.value}")
            print(f"Environment: {connection.metadata.environment.value}")
            print(f"Created by: {connection.metadata.created_by}")
            print(f"Created at: {connection.metadata.created_at}")
            print(f"Updated at: {connection.metadata.updated_at}")
            print(f"Usage count: {connection.metadata.usage_count}")
            print(
                f"Tags: {', '.join(connection.metadata.tags) if connection.metadata.tags else 'None'}"
            )
            print(f"Is active: {connection.metadata.is_active}")
            print(f"Is default: {connection.metadata.is_default}")

            # Display connection data (with sensitive data masked)
            print("\nConnection Data:")
            print("-" * 20)
            for key, value in connection.connection_data.items():
                if any(
                    sensitive in key.lower() for sensitive in ["key", "secret", "token"]
                ):
                    print(f"{key}: {'*' * 20}")
                else:
                    print(f"{key}: {value}")

        except Exception as e:
            logger.error(f"Error getting connection details: {e}")

    def delete_connection(self):
        """Delete a connection."""
        if not self.current_user:
            self._select_user()

        # Ensure user is selected (for type checking)
        if not self.current_user:
            print("User selection is required")
            return

        print(f"\nDELETE CONNECTION for {self.current_user}")
        print("=" * 60)

        try:
            connection_id = input("Enter Connection ID to delete: ").strip()
            if not connection_id:
                print("Connection ID is required")
                return

            # Confirm deletion
            confirm = (
                input(
                    f"Are you sure you want to delete connection '{connection_id}'? (y/n): "
                )
                .strip()
                .lower()
            )
            if confirm != "y":
                print("Deletion cancelled")
                return

            success = self.connection_manager.delete_connection(
                self.current_user, connection_id
            )

            if success:
                logger.success(f"Successfully deleted connection '{connection_id}'")
            else:
                print(f"Failed to delete connection '{connection_id}'")

        except Exception as e:
            logger.error(f"Error deleting connection: {e}")

    def test_connection_usage(self):
        """Test recording connection usage."""
        if not self.current_user:
            self._select_user()

        # Ensure user is selected (for type checking)
        if not self.current_user:
            print("User selection is required")
            return

        print(f"\nTEST CONNECTION USAGE for {self.current_user}")
        print("=" * 60)

        try:
            connection_id = input("Enter Connection ID: ").strip()
            if not connection_id:
                print("Connection ID is required")
                return

            # Record usage
            success = self.connection_manager.record_connection_usage(
                self.current_user, connection_id
            )

            if success:
                logger.success(
                    f"Successfully recorded usage for connection '{connection_id}'"
                )

                # Get usage stats
                stats = self.connection_manager.get_connection_usage_stats(
                    self.current_user, connection_id
                )
                if stats:
                    print("\nUsage Statistics:")
                    print(f"Total usage: {stats.total_usage}")
                    print(f"Last used: {stats.last_used}")
            else:
                print(f"Failed to record usage for connection '{connection_id}'")

        except Exception as e:
            logger.error(f"Error testing connection usage: {e}")

    def _display_connection_summary(
        self, connection_id: str, name: str, environment: str, tags: list[str]
    ):
        """Display connection creation summary."""
        print("\nConnection Summary")
        print("-" * 30)
        print(f"ID: {connection_id}")
        print(f"Name: {name}")
        print(f"Environment: {environment}")
        print(f"Tags: {', '.join(tags) if tags else 'None'}")
        print(f"User: {self.current_user}")

    def run(self):
        """Run the CLI."""
        print("RAG Config Manager - Vault Connection CLI")
        print("=" * 60)

        while True:
            print(f"\nCurrent User: {self.current_user or 'None selected'}")
            print("\nAvailable Operations:")
            print("1. Select User")
            print("2. Create Azure OpenAI Connection")
            print("3. Create AWS Connection")
            print("4. List Connections")
            print("5. Get Connection Details")
            print("6. Delete Connection")
            print("7. Test Connection Usage")
            print("8. Exit")

            choice = input("\nSelect option (1-8): ").strip()

            if choice == "1":
                self._select_user()
            elif choice == "2":
                self.create_azure_openai_connection()
            elif choice == "3":
                self.create_aws_connection()
            elif choice == "4":
                self.list_connections()
            elif choice == "5":
                self.get_connection_details()
            elif choice == "6":
                self.delete_connection()
            elif choice == "7":
                self.test_connection_usage()
            elif choice == "8":
                logger.info("👋 Goodbye!")
                break
            else:
                print("Invalid option. Please try again.")


if __name__ == "__main__":
    try:
        cli = VaultConnectionCLI()
        cli.run()
    except KeyboardInterrupt:
        logger.info("\nExiting...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
