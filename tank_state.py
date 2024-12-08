
global dissociationRate
dissociationRate = 0.5

# map from symbolic names of coils, direct inputs, input registers to the
# index in the tankState array that holds the values
# Added coils 2 and 3, and register 1
global coilMap
coilMap = {'CLIENT-CMD':0} # Client cmd to open or close HCl pump
global inputMap
inputMap =  {'HCL':0} # Actual pump value
global registerMap
registerMap = {'H-CONCENTRATION':0, "HCL-CONCENTRATION": 1} # CONCENTRATIONs are in mol/L * 10^9

class TankStateClass:
    def __init__(self):
        self.h_concentration = 0
        self.hcl_concentration = 0
    
    def set_h_concentration(self, h_concentration):
        self.h_concentration = h_concentration

    def set_hcl_concentration(self, hcl_concentration):
        self.hcl_concentration = hcl_concentration
    
    def get_concentrations(self):
        return (self.h_concentration, self.hcl_concentration)


    # def update_state(self, dilutionRate):


    def update_state(self, tankState, inputRate, dilutionRate):

        print("In module {}, {}, {}".format(tankState, inputRate, dilutionRate))

        if tankState['inputs'][inputMap['HCL']]:
                self.hcl_concentration += inputRate

        self.h_concentration += dissociationRate * self.hcl_concentration
        self.hcl_concentration  = (1 - dissociationRate) * self.hcl_concentration

        self.hcl_concentration = (1 - dilutionRate) * self.hcl_concentration

        return (self.h_concentration, self.hcl_concentration)
