
global dissociationRate
dissociationRate = 0.5

# map from symbolic names of coils, direct inputs, input registers to the
# index in the tankState array that holds the values
# Added coils 2 and 3, and register 1
global coilMap, inputMap, registerMap, initCoils, initInputs, initRegs
coilMap = {'CLIENT-CMD':0} # Client cmd to open or close HCl pump
inputMap =  {'HCL':0} # Actual pump value
registerMap = {'H-CONCENTRATION':0, "HCL-CONCENTRATION": 1} # CONCENTRATIONs are in mol/L * 10^9

initCoils = [1]
initInputs = [1]
initRegs = [0] * 2


class TankStateClass:
    def __init__(self):
        # self.h_concentration = 0
        # self.hcl_concentration = 0
        self.tankState = {'coils':initCoils, 'inputs':initInputs, 'registers':initRegs}
    
    def set_hcl_input(self, hcl):
        self.tankState['inputs'][inputMap['HCL']] = hcl

    def set_h_concentration(self, h_concentration):
        self.tankState['registers'][registerMap['H-CONCENTRATION']] = h_concentration

    def set_hcl_concentration(self, hcl_concentration):
        self.tankState['registers'][registerMap['HCL-CONCENTRATION']] = hcl_concentration
    
    def get_concentrations(self):
        return (self.tankState['registers'][registerMap['H-CONCENTRATION']], self.tankState['registers'][registerMap['HCL-CONCENTRATION']])

    def get_tank_state(self):
        return self.tankState

    # def update_state(self, dilutionRate):


    def update_state(self, inputRate, dilutionRate):

        print("Got here")
        # print("In module {}, {}, {}".format(inputRate, dilutionRate))

        if self.tankState['inputs'][inputMap['HCL']]:
            self.tankState['registers'][registerMap['HCL-CONCENTRATION']] += inputRate

        self.tankState['registers'][registerMap['H-CONCENTRATION']] += dissociationRate * self.tankState['registers'][registerMap['HCL-CONCENTRATION']]
        self.tankState['registers'][registerMap['HCL-CONCENTRATION']]  = (1 - dissociationRate) * self.tankState['registers'][registerMap['HCL-CONCENTRATION']]

        self.tankState['registers'][registerMap['HCL-CONCENTRATION']] = (1 - dilutionRate) * self.tankState['registers'][registerMap['HCL-CONCENTRATION']]

        return (self.tankState['registers'][registerMap['H-CONCENTRATION']], self.tankState['registers'][registerMap['HCL-CONCENTRATION']])
