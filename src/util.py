""" Utility methods and classes used by other modules """
class all_elements_satisfy(object):
    """
    Custom condition to use for verifying that all Selenium web
    elements match a certain condition
    """

    def __init__(self, locator, condition):
        self.locator = locator
        self.condition = condition

    def __call__(self, driver):
        elements = driver.find_elements(*self.locator)
        return all(self.condition(element) for element in elements)