import BackArrowButton from "assets/BackArrowButton";
import LLMConnectionForm, { LLMConnectionFormData } from "components/molecules/LLMConnectionForm";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useDialog } from 'hooks/useDialog';
import { createLLMConnection } from 'services/llmConnections';
import { llmConnectionsQueryKeys } from 'utils/queryKeys';
import { ButtonAppearanceTypes } from 'enums/commonEnums';
import { Button } from 'components';

const CreateLLMConnection = () => {
    const navigate = useNavigate();
    const { open: openDialog, close: closeDialog } = useDialog();
    const queryClient = useQueryClient();
    
    const createConnectionMutation = useMutation({
      mutationFn: createLLMConnection,
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: llmConnectionsQueryKeys.all()
        });
        
        openDialog({
          title: 'Connection Succeeded',
          content: <p>The provide LLM configuration is successfully configured</p>,
          footer: (
            <Button
              appearance={ButtonAppearanceTypes.PRIMARY}
              onClick={() => {
                closeDialog();
                navigate('/llm-connections');
              }}
            >
              View LLM Connections
            </Button>
          ),
        });
      },
      onError: (error: any) => {
        console.error('Error creating LLM connection:', error);
        openDialog({
          title: 'Connection Failed',
          content: <p>{'The connection couldn’t be established either due to invalid API credentials or misconfiguration in the deployment platform'}</p>,
          footer: (
            <Button
              appearance={ButtonAppearanceTypes.PRIMARY}
              onClick={closeDialog}
            >
              Go Back
            </Button>
          ),
        });
      },
    });
    
    const handleSubmit = async (data: LLMConnectionFormData) => {
      createConnectionMutation.mutate(data);
    };
    
    const handleCancel = () => {
      navigate('/llm-connections');
    };

    return(
        <div className="container">
        <div className="title_container">
          <div className="flex-grid">
            <Link to={'/llm-connections'}>
              <BackArrowButton />
            </Link>
            <div className="title">{'Create LLM Connection'}</div>
          </div>
        </div>
        <LLMConnectionForm
        onSubmit={handleSubmit}
        onCancel={handleCancel}
        isEditing={false}
        onDelete={() => {}}
      />
        </div>

    )
}

export default CreateLLMConnection;