# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-01-15

### Added
- Initial release of NEMO MQTT Plugin
- Real-time MQTT publishing for NEMO tool usage events
- Redis bridge architecture for reliable message delivery
- Web-based monitoring dashboard at `/mqtt/monitor/`
- Comprehensive configuration interface at `/customization/mqtt/`
- Support for tool events (creation, updates, enable/disable)
- Support for usage events (start/end with timing)
- Support for area access and reservation events
- SSL/TLS encryption support with certificate management
- Authentication support (username/password and certificates)
- Event filtering and custom topic configuration
- Quality of Service (QoS) level configuration
- Message retention and clean session options
- Auto-reconnection with exponential backoff
- Comprehensive logging and message audit trail
- Development mode with auto-service management
- Production deployment with systemd service support
- Docker Compose configuration for easy deployment
- Management commands for setup and testing
- Command-line monitoring and debugging tools
- Full test suite with pytest
- Type hints and code quality tools (Black, isort, flake8, mypy)
- Comprehensive documentation and usage examples

### Features
- **Easy Integration**: One-command installation with automatic setup
- **Robust Architecture**: Redis bridge prevents Django connection issues
- **Real-time Monitoring**: Web dashboard with live message display
- **Security**: Full TLS/SSL support with certificate management
- **Reliability**: Automatic reconnection and error recovery
- **Flexibility**: Configurable topics, QoS, and event filtering
- **Development**: Auto-starts Redis, MQTT broker, and services
- **Production**: Systemd service and Docker deployment support

### Technical Details
- Python 3.8+ support
- Django 3.2+ compatibility
- MQTT 3.1.1 and 5.0 support
- Redis 6.0+ for message queuing
- Comprehensive test coverage
- Type safety with mypy
- Code formatting with Black and isort
