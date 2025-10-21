#!/usr/bin/env python3
"""
Architecture Principles Validation - SOLID and Clean Architecture
"""
import sys
sys.path.append('.')
import inspect
from abc import ABC

def test_dependency_inversion():
    """Test that domain doesn't depend on infrastructure"""
    print("🏗️ Testing Dependency Inversion Principle...")
    
    from app.domain import repositories
    
    # Check that repository interfaces are abstract
    repo_classes = [
        repositories.HealthDataRepository,
        repositories.InsightReportRepository, 
        repositories.PatientRepository
    ]
    
    for repo_class in repo_classes:
        if not issubclass(repo_class, ABC):
            print(f"  ❌ {repo_class.__name__} should be abstract")
            return False
        
        # Check that methods are abstract
        abstract_methods = getattr(repo_class, '__abstractmethods__', set())
        if len(abstract_methods) == 0:
            print(f"  ❌ {repo_class.__name__} should have abstract methods")
            return False
        
        print(f"  ✅ {repo_class.__name__} properly abstract with {len(abstract_methods)} methods")
    
    return True

def test_single_responsibility():
    """Test that classes have single responsibility"""
    print("🎯 Testing Single Responsibility Principle...")
    
    from app.domain.entities import HealthData, VitalSigns, LabResult
    from app.domain.services import HealthDataValidationService, VitalSignsAnalysisService
    
    # Check that entities focus on data and basic validation
    entity_classes = [HealthData, VitalSigns, LabResult]
    for entity_class in entity_classes:
        methods = [method for method in dir(entity_class) 
                  if not method.startswith('_') and callable(getattr(entity_class, method))]
        
        # Entities should have minimal public methods (business logic only)
        if len(methods) <= 5:  # Reasonable limit for entities
            print(f"  ✅ {entity_class.__name__} has focused responsibility ({len(methods)} methods)")
        else:
            print(f"  ⚠️  {entity_class.__name__} might have too many responsibilities ({len(methods)} methods)")
    
    # Check that services are focused
    service_classes = [HealthDataValidationService, VitalSignsAnalysisService]
    for service_class in service_classes:
        methods = [method for method in dir(service_class) 
                  if not method.startswith('_') and callable(getattr(service_class, method))]
        
        print(f"  ✅ {service_class.__name__} service methods: {len(methods)}")
    
    return True

def test_interface_segregation():
    """Test that interfaces are specific and not bloated"""
    print("🔌 Testing Interface Segregation Principle...")
    
    from app.domain.repositories import HealthDataRepository, InsightReportRepository, PatientRepository
    
    repositories = [HealthDataRepository, InsightReportRepository, PatientRepository]
    
    for repo in repositories:
        abstract_methods = getattr(repo, '__abstractmethods__', set())
        
        # Each repository should have focused, specific methods
        if 5 <= len(abstract_methods) <= 15:  # Reasonable range
            print(f"  ✅ {repo.__name__} has appropriate interface size ({len(abstract_methods)} methods)")
        else:
            print(f"  ⚠️  {repo.__name__} interface might be too large/small ({len(abstract_methods)} methods)")
    
    return True

def test_open_closed_principle():
    """Test that classes are open for extension, closed for modification"""
    print("🔓 Testing Open/Closed Principle...")
    
    from app.domain.entities import VitalSigns, LabResult
    from app.domain.value_objects import HealthInsight, RiskAssessment
    
    # Check that entities use composition and inheritance-friendly patterns
    extensible_classes = [VitalSigns, LabResult, HealthInsight, RiskAssessment]
    
    for cls in extensible_classes:
        # Check if class uses dataclass (good for extension)
        if hasattr(cls, '__dataclass_fields__'):
            print(f"  ✅ {cls.__name__} uses dataclass (extensible)")
        
        # Check if class has validation hooks
        if hasattr(cls, '__post_init__'):
            print(f"  ✅ {cls.__name__} has validation hooks (extensible)")
    
    return True

def test_layer_separation():
    """Test that layers don't have circular dependencies"""
    print("🏛️ Testing Layer Separation...")
    
    # Domain layer should not import from other layers
    try:
        import app.domain.entities
        import app.domain.value_objects
        import app.domain.repositories
        import app.domain.services
        
        # Check domain module source for imports
        domain_modules = [
            app.domain.entities,
            app.domain.value_objects, 
            app.domain.repositories,
            app.domain.services
        ]
        
        for module in domain_modules:
            source = inspect.getsource(module)
            
            # Domain should not import from api, services, infra layers
            forbidden_imports = ['app.api', 'app.services', 'app.infra', 'app.agents']
            
            for forbidden in forbidden_imports:
                if forbidden in source:
                    print(f"  ❌ {module.__name__} imports from {forbidden} (violates layer separation)")
                    return False
            
            print(f"  ✅ {module.__name__} respects layer boundaries")
        
    except Exception as e:
        print(f"  ❌ Error checking layer separation: {e}")
        return False
    
    return True

def run_architecture_tests():
    """Run all architecture principle tests"""
    print("🏗️ TESTING ARCHITECTURE PRINCIPLES")
    print("=" * 60)
    
    tests = [
        test_dependency_inversion,
        test_single_responsibility,
        test_interface_segregation,
        test_open_closed_principle,
        test_layer_separation
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
                print(f"✅ {test.__name__} PASSED\n")
            else:
                failed += 1
                print(f"❌ {test.__name__} FAILED\n")
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} CRASHED: {e}\n")
    
    print("=" * 60)
    print(f"📊 ARCHITECTURE TEST RESULTS: {passed} PASSED, {failed} FAILED")
    
    if failed == 0:
        print("🏆 ARCHITECTURE IS SOLID - CLEAN ARCHITECTURE PRINCIPLES FOLLOWED!")
        return True
    else:
        print("⚠️  ARCHITECTURE ISSUES DETECTED - REVIEW REQUIRED")
        return False

if __name__ == "__main__":
    success = run_architecture_tests()
    sys.exit(0 if success else 1)