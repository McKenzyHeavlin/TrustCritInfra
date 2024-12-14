

class StatelessDetector:
    def __init__(self, threshold = 0):
        self.threshold = threshold

    def set_threshold(self, thredhold):
        self.threshold = thredhold
    
    def detect(self, actual, predicted):
        if abs(actual - predicted) > self.threshold:
            return True
        else:
            return False
        
class StatefulDetector:
    def __init__(self, threshold = 0):
        self.threshold = threshold
        self.residual = 0
        self.delta = 0

        self.deviation = 0
        self.detected = 0
    
    def set_threshold(self, thredhold):
        self.threshold = thredhold
    
    def set_residual(self, residual):
        self.residual = residual
    
    def set_delta(self, delta):
        self.delta = delta

    def get_delta(self):
        return self.delta

    def get_deviation(self):
        return self.deviation

    def detect(self, actual, predicted):
        self.residual += abs(actual - predicted)
        self.residual -= self.delta
        self.residual = 0 if self.residual < 0 else self.residual

        if self.residual > self.threshold:
            self.deviation
            self.detected = 1
            return True
        else:
            self.deviation += 0 if self.detected == 1 else abs(actual - predicted)
            return False