import { Button, Container, Row, Spacer, Text } from "@nextui-org/react";
import Decimal from "decimal.js";
import { BigNumber } from "ethers";
import { isAddress } from "ethers/lib/utils";
import { useState, useMemo } from "react";
import { erc20ABI, useBalance, useContract, useNetwork, useSigner } from "wagmi";
import { TextField } from "../components/TextField";
import { mainnet, ropsten } from 'wagmi/chains'

interface SwapWncgPageProps {
    address: string,
};

const SwapWncgPage: React.FC<SwapWncgPageProps> = ({ address }) => {
  const { chain } = useNetwork();

  const contractAddress = useMemo<string>(() => {
    if (chain?.id === mainnet.id) {
      return "0xf203ca1769ca8e9e8fe1da9d147db68b6c919817";
    } else if (chain?.id === ropsten.id) {
      return "0xeaa982f3424338598738c496153e55b1df11f625";
    } else {
      return "0x5F2e568E7085Ce18fA7b68e13fd5C04e99F044C4";
    }
  }, [chain]);

  const { data, isLoading, error } = useBalance({
    addressOrName: address,
    token: contractAddress,
  });

  const { data: signer } = useSigner();
  const contract = useContract({
    addressOrName: contractAddress,
    contractInterface: [
        "function burn(uint256 amount, bytes32 to) public",
        ...erc20ABI,
    ],
    signerOrProvider: signer,
  });

  const [ncAddress, setNcAddress] = useState<string>("");
  const [amount, setAmount] = useState<string>("0");
  const burnAmount = useMemo<Decimal | null>(() => {
    try {
      return new Decimal(amount || "0").mul(new Decimal(10).pow(18))
    } catch {
      return null;
    }
  }, [amount]);

  return (
    <Container style={{
      margin: "30vh 0",
      minWidth: "100%",
      overflow: "hidden",
    }}>
      <Row justify="center">
        <Text>Your wNCG : {
          isLoading
            ? <Text span={true}>🕑</Text>
            : <Text weight="bold" span={true}>{
                  data !== undefined
                      ? new Decimal(data.value.toString()).div(new Decimal(10).pow(data.decimals)).toString()
                      : error?.message
              }</Text>
        }</Text>
      </Row>
      <Spacer />
      <Spacer />
      <Row justify="center">
        <TextField label={'To'} onChange={setNcAddress}/>
      </Row>
      <Spacer />
      <Row justify="center">
        <TextField label={'Amount'} onChange={setAmount}/>
      </Row>
      <Spacer />
      <Row justify="center">
        {
          contract === null || burnAmount === null || burnAmount.toString().indexOf(".") !== -1 || !isAddress(ncAddress)
            ? <Text weight={"bold"}>Fill corret values</Text>
            : <Button onClick={event => {
              event.preventDefault();    
              console.log(contract);
              contract.burn(BigNumber.from(burnAmount.toString()), ncAddress + "0".repeat(24)).then(console.debug)
            }}>Burn</Button>
        }
      </Row>
    </Container>
  );
}

export default SwapWncgPage;
