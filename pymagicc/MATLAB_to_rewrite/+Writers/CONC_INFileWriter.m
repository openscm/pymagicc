classdef CONC_INFileWriter < object_oriented_simcap.Writers.MAGICCDataFileWriter
    methods (Access = protected)
        function file_header_formatted = get_file_header(self)
            file_header = [...
                '.__  __          _____ _____ _____ _____ ______    _____ ____  _   _  _____   _____ _   _' self.newline_char...
                '|  \/  |   /\   / ____|_   _/ ____/ ____|____  |  / ____/ __ \| \ | |/ ____| |_   _| \ | |' self.newline_char...
                '| \  / |  /  \ | |  __  | || |   | |        / /  | |   | |  | |  \| | |        | | |  \| |' self.newline_char...
                '| |\/| | / /\ \| | |_ | | || |   | |       / /   | |   | |  | | . ` | |        | | | . ` |' self.newline_char...
                '| |  | |/ ____ \ |__| |_| || |___| |____  / /    | |___| |__| | |\  | |____ _ _| |_| |\  |' self.newline_char...
                '|_|  |_/_/    \_\_____|_____\_____\_____|/_/      \_____\____/|_| \_|\_____(_)_____|_| \_|'...
            ];
            file_header_formatted = object_oriented_simcap.Utils.return_sprintf_compatible_string(...
                file_header...
            );
        end
        function renamed_cell_datablock = return_renamed_cell_datablock(self,cell_datablock)
            renamed_cell_datablock = return_renamed_cell_datablock@object_oriented_simcap.Writers.MAGICCDataFileWriter(...
                self,cell_datablock...
            );
            WORLD_idx = strcmpi(renamed_cell_datablock,'WORLD');
            renamed_cell_datablock{WORLD_idx} = 'GLOBAL_MIXINGRATIO';
        end
        function Data_value = return_Data_descriptor(self)
            return_Data_descriptor@object_oriented_simcap.Writers.MAGICCDataFileWriter(self);
            gas_descriptor = self.return_Gas_descriptor;
            if strcmp(gas_descriptor,'multiple')
                error('I shouldn''t be able to get here for a CONC.IN file')
            else
                Data_value = 'Global average mixing ratio';
            end
        end
        function set_THISFILE_DATTYPE_THISFILE_REGIONMODE_region_column_order(self)
            set_THISFILE_DATTYPE_THISFILE_REGIONMODE_region_column_order@object_oriented_simcap.Writers.MAGICCDataFileWriter(self)
            % will be able to remove this hard coding in future once we
            % work out our conventions better
            self.THISFILE_DATTYPE = 'NOTUSED';
            self.THISFILE_REGIONMODE = 'FOURBOX';
        end
    end
end